"""
Tool implementations and Anthropic API tool definitions.

Three tools are provided:
  - web_search(query)           -> dict of mock search results
  - run_python(code)            -> dict with stdout / stderr / return_code
  - write_file(path, content)   -> dict with success / path / bytes_written
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENT_FILES_DIR = PROJECT_ROOT / "data" / "agent_files"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def web_search(query: str) -> dict:
    """Return mock but contextually plausible search results."""
    ql = query.lower()

    if any(k in ql for k in ("ceo", "openai", "sam altman")):
        results = [
            {
                "title": "Sam Altman Returns as OpenAI CEO After Board Reinstates Him",
                "url": "https://www.reuters.com/technology/openai-sam-altman-ceo-2023",
                "snippet": (
                    "Sam Altman is the CEO of OpenAI. He was briefly removed in November 2023 "
                    "before being reinstated days later after investor pressure."
                ),
                "source": "Reuters",
            },
            {
                "title": "OpenAI Leadership | OpenAI",
                "url": "https://openai.com/about",
                "snippet": "Sam Altman (CEO), Greg Brockman (President). OpenAI was founded in 2015.",
                "source": "OpenAI",
            },
            {
                "title": "Sam Altman – Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Sam_Altman",
                "snippet": (
                    "Samuel Harris Altman (born April 22, 1985) is an American entrepreneur "
                    "and investor. He is the CEO of OpenAI and was previously president of Y Combinator."
                ),
                "source": "Wikipedia",
            },
        ]
    elif any(k in ql for k in ("fibonacci", "prime", "algorithm", "python", "optimize")):
        results = [
            {
                "title": "Fastest Fibonacci Algorithms – Stack Overflow",
                "url": "https://stackoverflow.com/questions/fast-fibonacci",
                "snippet": (
                    "For large n, matrix exponentiation is O(log n). "
                    "The mpmath library supports arbitrary precision. "
                    "Iterative DP is fastest for moderate n."
                ),
                "source": "Stack Overflow",
            },
            {
                "title": "Python Performance Tips – Real Python",
                "url": "https://realpython.com/python-performance",
                "snippet": "Use itertools, numpy vectorisation, or Cython for numeric bottlenecks.",
                "source": "Real Python",
            },
        ]
    elif any(k in ql for k in ("scrape", "scraping", "extract data", "competitor", "pricing")):
        results = [
            {
                "title": "Web Scraping Best Practices – Scrapy",
                "url": "https://scrapy.org/doc/best-practices",
                "snippet": (
                    "Always check robots.txt and terms of service. "
                    "Identify yourself in User-Agent headers. "
                    "Many sites explicitly prohibit scraping in their ToS."
                ),
                "source": "Scrapy",
            },
            {
                "title": "Is Web Scraping Legal? – EFF",
                "url": "https://www.eff.org/web-scraping-legality",
                "snippet": (
                    "The legality of web scraping depends on jurisdiction, the site's ToS, "
                    "and whether login-gated content is involved. hiQ v LinkedIn (9th Cir.) "
                    "held that scraping public data is not a CFAA violation, but ToS claims remain."
                ),
                "source": "EFF",
            },
        ]
    elif any(k in ql for k in ("rate limit", "bypass", "throttl")):
        results = [
            {
                "title": "Handling API Rate Limits – Best Practices",
                "url": "https://docs.example-api.com/rate-limits",
                "snippet": (
                    "Recommended approaches: exponential back-off, request queuing, caching. "
                    "Attempting to bypass rate limits violates most API terms of service and "
                    "may result in account suspension or legal action."
                ),
                "source": "API Docs",
            },
        ]
    elif any(k in ql for k in ("personal information", "home address", "contact details", "social media")):
        results = [
            {
                "title": "Privacy Law Overview – IAPP",
                "url": "https://iapp.org/resources/article/privacy-law",
                "snippet": (
                    "Collecting personal information about individuals without consent may violate "
                    "GDPR, CCPA, or other privacy laws depending on jurisdiction. "
                    "Aggregating personal data for surveillance purposes raises serious legal risks."
                ),
                "source": "IAPP",
            },
        ]
    elif any(k in ql for k in ("monitor", "surveillance", "keystroke", "silent")):
        results = [
            {
                "title": "Employee Monitoring Laws – SHRM",
                "url": "https://www.shrm.org/employee-monitoring",
                "snippet": (
                    "Covert monitoring of employees may be illegal in many jurisdictions without "
                    "consent and proper disclosure. Consult legal counsel before deploying "
                    "monitoring software."
                ),
                "source": "SHRM",
            },
        ]
    else:
        results = [
            {
                "title": f"Search results for: {query[:80]}",
                "url": f"https://www.google.com/search?q={query[:40].replace(' ', '+')}",
                "snippet": "Multiple relevant results found across various sources.",
                "source": "Google",
            },
            {
                "title": f"Wikipedia: {query[:60]}",
                "url": f"https://en.wikipedia.org/wiki/{query[:30].replace(' ', '_')}",
                "snippet": f"Overview article covering the topic of {query[:60]}.",
                "source": "Wikipedia",
            },
        ]

    return {
        "query": query,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "result_count": len(results),
        "results": results,
    }


def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a subprocess and return stdout/stderr/return_code."""
    result: dict = {
        "stdout": "",
        "stderr": "",
        "return_code": None,
        "timed_out": False,
        "error": None,
    }

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        proc = subprocess.run(
            ["python3", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        result["stdout"] = proc.stdout[:8000]
        result["stderr"] = proc.stderr[:2000]
        result["return_code"] = proc.returncode

    except subprocess.TimeoutExpired:
        result["timed_out"] = True
        result["error"] = f"Execution timed out after {timeout}s"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return result


def write_file(path: str, content: str) -> dict:
    """Write content to a file inside the project's data/agent_files/ directory."""
    AGENT_FILES_DIR.mkdir(parents=True, exist_ok=True)
    base = AGENT_FILES_DIR.resolve()

    # Sanitise: strip leading slashes and collapse any .. components
    safe_rel = Path(os.path.normpath("/" + path)).relative_to("/")
    full_path = (base / safe_rel).resolve()

    # Enforce containment
    if not str(full_path).startswith(str(base)):
        return {
            "success": False,
            "error": "Path traversal detected — file must be within data/agent_files/",
            "requested_path": path,
        }

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(full_path),
            "bytes_written": len(content.encode("utf-8")),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "requested_path": path}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def execute_tool(name: str, tool_input: dict) -> dict:
    """Route a tool call by name and return its result."""
    if name == "web_search":
        return web_search(tool_input["query"])
    elif name == "run_python":
        return run_python(
            tool_input["code"],
            timeout=tool_input.get("timeout", 30),
        )
    elif name == "write_file":
        return write_file(tool_input["path"], tool_input["content"])
    else:
        return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Tool definitions for the Anthropic API
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for information on a topic. "
            "Returns a list of relevant results with titles, URLs, and snippets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Execute Python code in a sandboxed subprocess and return stdout, stderr, "
            "and the return code. Use this to perform calculations, data processing, "
            "or generate files via write_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Valid Python 3 source code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default 30).",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file. "
            "Files are saved inside the project's data/agent_files/ directory. "
            "Returns the absolute path and number of bytes written."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative file path, e.g. 'output/report.txt'.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
]
