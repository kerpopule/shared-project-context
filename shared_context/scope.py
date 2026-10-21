"""Explicit process-local MCP capability restrictions, independent of client names.

A scope restricts this server connection, not other programs run by the same OS
account. Remote hosts must authenticate and authorize before creating a scope.
"""

from dataclasses import dataclass
import json
from typing import Optional

from .api import dispatch, schemas
from .core import ContextError, Store

READ_OPERATIONS = frozenset({"context", "read_reference", "list"})
SCOPED_OPERATIONS = READ_OPERATIONS | {"begin", "checkpoint", "finish"}


@dataclass(frozen=True)
class Scope:
    project: Optional[str] = None
    read_only: bool = False
    actor: Optional[str] = None
    session: Optional[str] = None

    def __post_init__(self):
        for value in (self.project, self.actor, self.session):
            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 4096
                or any(ord(char) < 32 for char in value)
            ):
                raise ContextError("invalid_scope")
        if type(self.read_only) is not bool:
            raise ContextError("invalid_scope")
        if bool(self.actor) != bool(self.session):
            raise ContextError("actor_and_session_required_together")
        if self.actor and not self.project:
            raise ContextError("identity_binding_requires_project")
        if any(
            value is not None
            and (not isinstance(value, str) or not 1 <= len(value) <= 200)
            for value in (self.actor, self.session)
        ):
            raise ContextError("invalid_bound_identity")

    def tools(self):
        tools = [tool for tool in schemas() if self.permits(tool["name"][8:])]
        for tool in tools:
            properties = tool["inputSchema"]["properties"]
            for name, value in (("actor", self.actor), ("session", self.session)):
                if value and name in properties:
                    properties[name]["const"] = value
        return tools

    def permits(self, operation):
        if self.read_only and operation not in READ_OPERATIONS:
            return False
        return not self.project or operation in SCOPED_OPERATIONS

    def call(self, operation, arguments, store=None):
        if store is None:
            owned = Store()
            try:
                return self.call(operation, arguments, owned)
            finally:
                owned.db.close()
        if not isinstance(arguments, dict):
            raise ContextError("invalid_arguments")
        if not self.permits(operation):
            raise ContextError("operation_not_available")
        args = dict(arguments)
        if self.project:
            # Do not disclose whether an ungranted project, alias or path exists.
            try:
                row = store.resolve(self.project)
                if (
                    operation != "list"
                    and store.resolve(args.get("project"))["id"] != row["id"]
                ):
                    raise ContextError("project_not_available")
            except (ContextError, OSError, ValueError, TypeError):
                raise ContextError("project_not_available") from None
            if operation == "list":
                offset = args.get("offset", 0)
                if set(args) - {"offset"} or type(offset) is not int or offset < 0:
                    raise ContextError("invalid_offset")
                item = dict(row)
                item["aliases"] = json.loads(item["aliases"])
                return {
                    "projects": [item] if offset == 0 else [],
                    "has_more": False,
                    "next_offset": None,
                }
            # Use the canonical grant; workspace arguments still undergo core containment checks.
            args["project"] = row["id"]
        if self.actor and operation in {"begin", "checkpoint", "finish"}:
            for field, value in (("actor", self.actor), ("session", self.session)):
                if field in args and args[field] != value:
                    raise ContextError("identity_binding_mismatch")
                args[field] = value
        return dispatch(operation, args, store)
