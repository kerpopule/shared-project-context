"""Dependency-free MCP stdio transport (newline-delimited JSON-RPC). No listener."""

import json
import sys
import sqlite3
from . import __version__
from .api import GUIDANCE, dispatch, schemas
from .core import ContextError

MAX_FRAME = 128 * 1024


def respond(request):
    if not isinstance(request, dict) or "id" not in request:
        return None
    result = {"jsonrpc": "2.0", "id": request["id"]}
    method = request.get("method")
    if method == "initialize":
        requested = request.get("params", {}).get("protocolVersion")
        version = (
            requested
            if requested in {"2024-11-05", "2025-03-26", "2025-06-18"}
            else "2024-11-05"
        )
        result["result"] = {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "shared-project-context", "version": __version__},
            "instructions": GUIDANCE,
        }
    elif method == "ping":
        result["result"] = {}
    elif method == "tools/list":
        result["result"] = {"tools": schemas()}
    elif method == "tools/call":
        params = request.get("params", {})
        names = {x["name"] for x in schemas()}
        try:
            if params.get("name") not in names:
                raise ContextError("unknown_tool")
            value = dispatch(params["name"][8:], params.get("arguments", {}))
            body = {
                "content": [{"type": "text", "text": json.dumps(value)}],
                "isError": False,
            }
        except (ContextError, KeyError, TypeError, ValueError, OSError) as e:
            code = (
                str(e)
                if isinstance(e, ContextError)
                else "invalid_request_or_unavailable"
            )
            body = {
                "content": [{"type": "text", "text": json.dumps({"error": code})}],
                "isError": True,
            }
        except sqlite3.Error:
            body = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"error": "shared_context_store_unavailable"}
                        ),
                    }
                ],
                "isError": True,
            }
        result["result"] = body
    else:
        result["error"] = {"code": -32601, "message": "Method not found"}
    return result


def serve():
    while True:
        line = sys.stdin.buffer.readline(MAX_FRAME + 1)
        if not line:
            return
        if len(line) > MAX_FRAME:
            return  # Oversize peers must reconnect; never parse a frame fragment.
        try:
            output = respond(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError):
            output = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        if output is not None:
            print(json.dumps(output), flush=True)
