"""Run with python -m shared_context. No external runtime dependencies."""

import argparse
import json
import sqlite3
import sys
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
    for name in ("serve", "hook", "doctor", "uninstall"):
        sub.add_parser(name)
    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--clients", default="auto")
    setup_parser.add_argument("--reactivate", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            from .mcp import serve

            return serve()
        if args.command == "setup":
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
            except (ValueError, OSError, sqlite3.Error):
                text = "Shared project context unavailable; inspect the workspace rather than assuming no changes."
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
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
