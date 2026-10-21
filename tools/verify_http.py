"""Real loopback HTTP + official SDK probe. Run under a bounded process lease."""

import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.core import Store
from shared_context.http_transport import create_app


async def probe(root):
    import httpx2
    import uvicorn
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    os.environ["SHARED_CONTEXT_HOME"] = str(root / "state")
    store = Store()
    workspace = root / "workspace"
    workspace.mkdir()
    store.register("demo", str(workspace))
    store.checkpoint(
        "demo",
        actor="fixture",
        expected_revision=0,
        key="start",
        summary="HTTP canary project decision",
        status="proposed",
    )
    other = root / "other"
    other.mkdir()
    store.register("private", str(other), aliases=["PRIVATE_CANARY"])
    store.db.close()
    token = secrets.token_urlsafe(32)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/mcp"
    app = create_app("demo", token, port)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="error",
            access_log=False,
            timeout_keep_alive=2,
            timeout_graceful_shutdown=2,
            limit_concurrency=16,
        )
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    result = {}
    try:
        deadline = asyncio.get_running_loop().time() + 8
        while not server.started:
            if task.done() or asyncio.get_running_loop().time() > deadline:
                raise RuntimeError("fixture_server_start_failed")
            await asyncio.sleep(0.01)
        headers = {"Authorization": "bearer " + token}
        async with httpx2.AsyncClient(
            headers=headers, trust_env=False, timeout=10
        ) as client:
            async with streamable_http_client(url, http_client=client) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert {tool.name for tool in tools.tools} == {
                        "project_list",
                        "project_context",
                        "project_read_reference",
                    }
                    packet = await session.call_tool(
                        "project_context", {"project": "demo"}
                    )
                    assert (
                        not packet.is_error
                        and packet.structured_content["revision"] == 1
                    )
                    assert "HTTP canary" in str(packet.structured_content)
                    denied = await session.call_tool(
                        "project_context", {"project": "private"}
                    )
                    assert denied.is_error and "PRIVATE_CANARY" not in str(denied)
                    listed = await session.call_tool("project_list", {})
                    assert len(listed.structured_content["projects"]) == 1
                    resources = await session.list_resources()
                    assert resources.resources
                    prompt = await session.get_prompt(
                        "resume-project", arguments={"project": "demo"}
                    )
                    assert prompt.messages
            result["official_sdk_round_trip"] = True
        async with httpx2.AsyncClient(trust_env=False, timeout=10) as client:
            assert (await client.post(url, json={})).status_code == 401
            wrong = {"Authorization": "Bearer " + "w" * 43}
            assert (await client.post(url, headers=wrong, json={})).status_code == 401
            assert (
                await client.post(
                    url, headers={**headers, "Host": "evil.invalid"}, json={}
                )
            ).status_code == 403
            assert (
                await client.post(
                    url, headers={**headers, "Origin": "https://evil.invalid"}, json={}
                )
            ).status_code == 403
            assert (
                await client.post(url, headers=headers, content=b"x" * 131073)
            ).status_code == 413
            from unittest.mock import patch

            with patch(
                "shared_context.http_transport.hmac.compare_digest", return_value=True
            ):
                status = (await client.post(url, headers=wrong, json={})).status_code
                assert status != 401, (
                    "negative control did not disable the actual auth gate"
                )
        result.update(
            authentication_denials=True,
            origin_and_host_denials=True,
            oversized_request_denied=True,
            auth_negative_control=True,
            project_isolation=True,
            read_only_catalog=True,
            real_inference_calls=0,
        )
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=8)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            sock.close()
    result["fixture_listener_closed"] = sock.fileno() == -1
    result["pass"] = all(
        value is True for key, value in result.items() if key != "real_inference_calls"
    )
    return result


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="shared-context-http-") as directory:
        result = asyncio.run(probe(Path(directory)))
    print(json.dumps(result, indent=2))
