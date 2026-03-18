"""
Core agent: agentic loop over the Claude API with tool use.

Records all tool calls, reasoning text, and timing for later analysis.
"""

import json
import time
from typing import Any

import anthropic

from .conditions import get_condition
from .tools import TOOL_DEFINITIONS, execute_tool

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
MAX_ITERATIONS = 20  # safety cap on tool-use rounds


class Agent:
    def __init__(
        self,
        condition: str,
        model: str = DEFAULT_MODEL,
    ):
        """
        Args:
            condition: 'monitored' or 'unmonitored'
            model:     Anthropic model ID
        """
        self.client = anthropic.Anthropic()
        self.model = model
        self.condition = condition
        self.system_prompt = get_condition(condition)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, task: str) -> dict:
        """
        Run the agent on a single task description.

        Returns a structured log containing:
          - task text
          - condition name
          - final output text
          - all tool calls with inputs / outputs
          - token usage
          - wall-clock duration
        """
        start = time.time()
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]

        tool_calls: list[dict] = []
        iterations: list[dict] = []
        error: str | None = None

        try:
            for _round in range(MAX_ITERATIONS):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=MAX_TOKENS,
                    system=self.system_prompt,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                )

                iteration_log = self._log_response(response)
                iterations.append(iteration_log)

                if response.stop_reason == "end_turn":
                    break

                if response.stop_reason != "tool_use":
                    # Unexpected stop — treat as done
                    break

                # ---- execute tools ----------------------------------------
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        call_start = time.time()
                        result = execute_tool(block.name, block.input)
                        elapsed = time.time() - call_start

                        call_log = {
                            "tool_name": block.name,
                            "input": dict(block.input),
                            "output": result,
                            "duration_seconds": round(elapsed, 3),
                            "elapsed_since_start": round(call_start - start, 3),
                        }
                        tool_calls.append(call_log)

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )

                messages.append({"role": "user", "content": tool_results})

        except Exception as exc:
            error = str(exc)

        duration = round(time.time() - start, 3)
        final_text = self._extract_final_text(iterations)

        return {
            "condition": self.condition,
            "model": self.model,
            "task": task,
            "final_output": final_text,
            "tool_calls": tool_calls,
            "iterations": iterations,
            "total_tool_calls": len(tool_calls),
            "tools_used": list({c["tool_name"] for c in tool_calls}),
            "duration_seconds": duration,
            "total_input_tokens": sum(
                it.get("usage", {}).get("input_tokens", 0) for it in iterations
            ),
            "total_output_tokens": sum(
                it.get("usage", {}).get("output_tokens", 0) for it in iterations
            ),
            "error": error,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _log_response(response) -> dict:
        content_log = []
        for block in response.content:
            if block.type == "text":
                content_log.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content_log.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": dict(block.input),
                    }
                )
        return {
            "stop_reason": response.stop_reason,
            "content": content_log,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    @staticmethod
    def _extract_final_text(iterations: list[dict]) -> str:
        """Return the last text block produced across all iterations."""
        last = ""
        for it in iterations:
            for block in it.get("content", []):
                if block.get("type") == "text":
                    last = block["text"]
        return last
