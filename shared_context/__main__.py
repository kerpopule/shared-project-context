"""Run with python -m shared_context. No external runtime dependencies."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .api import dispatch
from .core import ContextError


def main():
    parser = argparse.ArgumentParser(
        description="Local shared project awareness, independent of client updates."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    call = sub.add_parser("call", help="Run a core operation with a JSON object.")
    call.add_argument("operation")
    call.add_argument("arguments", nargs="?", default="{}")
    for name in ("doctor", "uninstall"):
        sub.add_parser(name)
    hook = sub.add_parser("hook")
    hook.add_argument("--client", choices=("claude", "gemini"), default="claude")
    server = sub.add_parser(
        "serve", help="MCP stdio; optionally restrict this connection."
    )
    server.add_argument("--project")
    server.add_argument("--read-only", action="store_true")
    server.add_argument("--actor")
    server.add_argument("--session")
    http = sub.add_parser(
        "serve-http", help="Optional authenticated loopback MCP; no public listener."
    )
    http.add_argument("--project", required=True)
    http.add_argument("--port", type=int, default=8765)
    http.add_argument("--token-env", default="SHARED_CONTEXT_TOKEN")
    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--clients", default="auto")
    setup_parser.add_argument("--reactivate", action="store_true")
    from .clients import CLIENTS

    connect = sub.add_parser(
        "connect", help="Print client-specific configuration; makes no changes."
    )
    connect.add_argument("--client", required=True, choices=sorted(CLIENTS))
    connect.add_argument("--launcher")
    connect.add_argument("--project")
    connect.add_argument("--read-only", action="store_true")
    connect.add_argument("--actor")
    connect.add_argument("--session")
    connect.add_argument(
        "--ssh",
        help="Generate stdio-over-SSH using an existing authorized host; does not connect.",
    )
    room = sub.add_parser(
        "room-context", help="Read an explicit owner-configured room grant."
    )
    for field in ("config", "host", "room", "member", "session"):
        room.add_argument("--" + field, required=True)
    args = parser.parse_args()
    try:
        if args.command == "room-context":
            from .room_host import room_context

            result = room_context(
                args.config, args.host, args.room, args.member, args.session
            )
            # Hosts need the bounded prompt, not a duplicate serialized packet.
            print(
                json.dumps(
                    {key: result[key] for key in ("enabled", "context", "scope")}
                )
            )
            return 0
        if args.command == "serve-http":
            from .http_transport import run_http

            return run_http(args.project, args.port, args.token_env)
        if args.command == "serve":
            from .mcp import serve
            from .scope import Scope

            return serve(Scope(args.project, args.read_only, args.actor, args.session))
        if args.command == "connect":
            from .clients import connection
            from .core import default_home

            launcher = args.launcher or str(Path(default_home()) / "bin/shared-context")
            print(
                json.dumps(
                    connection(
                        args.client,
                        launcher,
                        project=args.project,
                        read_only=args.read_only,
                        actor=args.actor,
                        session=args.session,
                        ssh=args.ssh,
                    )
                )
            )
        elif args.command == "setup":
            from .install import setup

            clients = None if args.clients == "auto" else args.clients.split(",")
            print(json.dumps(setup(clients=clients, reactivate=args.reactivate)))
        elif args.command == "uninstall":
            from .install import uninstall

            print(json.dumps(uninstall()))
        elif args.command == "doctor":
            from .health import doctor

            result = doctor()
            print(json.dumps(result))
            return 0 if result["ok"] else 2
        elif args.command == "hook":
            from .hermes_adapter import entry_context

            try:
                event = json.loads(sys.stdin.readline(65536))
                text = entry_context(
                    cwd=event.get("cwd"), user_message=str(event.get("prompt", ""))
                )
            except (ValueError, TypeError, AttributeError, OSError, sqlite3.Error):
                text = "Shared project context unavailable; inspect the workspace rather than assuming no changes."
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "BeforeAgent"
                            if args.client == "gemini"
                            else "UserPromptSubmit",
                            "additionalContext": text,
                        }
                    }
                )
            )
        else:
            print(json.dumps(dispatch(args.operation, json.loads(args.arguments))))
        return 0
    except (ContextError, ValueError, TypeError) as error:
        print(json.dumps({"error": str(error)}))
        return 2
    except (OSError, sqlite3.Error):
        print(json.dumps({"error": "shared_context_unavailable"}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
