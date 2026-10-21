"""Optional authenticated loopback HTTP transport, using the official MCP SDK."""

import asyncio
from contextlib import asynccontextmanager
import hmac
import os
import sqlite3

from . import __version__
from .api import GUIDANCE
from .core import ContextError
from .mcp import MAX_FRAME, _handle
from .scope import Scope


def create_app(project, token, port, *, actor=None, session=None, read_only=True):
    """One explicit project/principal. This is not an OAuth or multi-tenant host."""
    if not project or not isinstance(token, str) or not 32 <= len(token) <= 512:
        raise ContextError("project_and_strong_token_required")
    if not token.isascii() or any(char.isspace() for char in token):
        raise ContextError("invalid_http_token")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ContextError("invalid_http_port")
    if not read_only and not (actor and session):
        raise ContextError("writable_http_requires_bound_identity")
    policy = Scope(project, read_only, actor, session)
    try:
        import anyio
        import mcp.types as types
        from mcp import MCPError
        from mcp.server import Server
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp.server.transport_security import TransportSecuritySettings
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
    except ImportError:
        raise ContextError("http_extra_required_python310_or_newer") from None

    def handler(method, result_type):
        async def invoke(context, params):
            arguments = (
                params.model_dump(mode="json", by_alias=True, exclude_none=True)
                if params
                else {}
            )
            try:
                result = await anyio.to_thread.run_sync(
                    lambda: _handle(method, arguments, policy)
                )
                return result_type.model_validate(result)
            except (
                ContextError,
                ValueError,
                TypeError,
                OSError,
                sqlite3.Error,
            ) as error:
                message = (
                    str(error)
                    if isinstance(error, ContextError)
                    else "context_unavailable"
                )
                raise MCPError(-32602, message) from None

        return invoke

    server = Server(
        "shared-project-context",
        version=__version__,
        instructions=GUIDANCE,
        on_list_tools=handler("tools/list", types.ListToolsResult),
        on_call_tool=handler("tools/call", types.CallToolResult),
        on_list_resources=handler("resources/list", types.ListResourcesResult),
        on_list_resource_templates=handler(
            "resources/templates/list", types.ListResourceTemplatesResult
        ),
        on_read_resource=handler("resources/read", types.ReadResourceResult),
        on_list_prompts=handler("prompts/list", types.ListPromptsResult),
        on_get_prompt=handler("prompts/get", types.GetPromptResult),
    )
    hosts = [f"127.0.0.1:{port}", f"localhost:{port}"]
    origins = ["http://" + host for host in hosts]
    manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
        max_request_body_size=MAX_FRAME,
        max_sessions=8,
        security_settings=TransportSecuritySettings(
            allowed_hosts=hosts, allowed_origins=origins
        ),
    )

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    class Endpoint:
        async def __call__(self, scope, receive, send):
            await manager.handle_request(scope, receive, send)

    transport = Starlette(routes=[Route("/mcp", Endpoint())], lifespan=lifespan)
    active = [0]

    async def guarded(scope, receive, send):
        if scope["type"] != "http":
            return await transport(scope, receive, send)
        headers = scope.get("headers", [])

        def values(key):
            return [value for name, value in headers if name.lower() == key]

        async def reject(status, message):
            response = PlainTextResponse(
                message,
                status_code=status,
                headers={"WWW-Authenticate": 'Bearer realm="shared-project-context"'}
                if status == 401
                else {},
            )
            await response(scope, receive, send)

        if scope.get("path") != "/mcp":
            return await reject(404, "not_found")
        host = values(b"host")
        origin = values(b"origin")
        if len(host) != 1 or host[0].decode("latin1") not in hosts:
            return await reject(403, "host_not_allowed")
        if len(origin) > 1 or (origin and origin[0].decode("latin1") not in origins):
            return await reject(403, "origin_not_allowed")
        authorization = values(b"authorization")
        credentials = authorization[0].split(b" ", 1) if len(authorization) == 1 else []
        if (
            len(credentials) != 2
            or credentials[0].lower() != b"bearer"
            or not hmac.compare_digest(credentials[1], token.encode("ascii"))
        ):
            return await reject(401, "authentication_required")
        length = values(b"content-length")
        try:
            if len(length) > 1 or (
                length and (int(length[0]) < 0 or int(length[0]) > MAX_FRAME)
            ):
                return await reject(413, "request_too_large")
        except ValueError:
            return await reject(400, "invalid_content_length")
        if active[0] >= 8:
            return await reject(503, "request_capacity")
        active[0] += 1
        started = [False]

        async def tracked_send(message):
            if message["type"] == "http.response.start":
                started[0] = True
            await send(message)

        try:
            await asyncio.wait_for(transport(scope, receive, tracked_send), timeout=30)
        except asyncio.TimeoutError:
            if not started[0]:
                await reject(504, "outcome_unknown_use_same_retry_key")
        finally:
            active[0] -= 1

    return guarded


def run_http(project, port=8765, token_env="SHARED_CONTEXT_TOKEN"):
    try:
        import uvicorn
    except ImportError:
        raise ContextError("http_extra_required_python310_or_newer") from None
    app = create_app(project, os.environ.get(token_env), port)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        access_log=False,
        limit_concurrency=16,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=5,
    )
