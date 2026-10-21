import asyncio
import unittest

from shared_context.core import ContextError
from shared_context.http_transport import create_app


class HttpContractTest(unittest.TestCase):
    def test_invalid_startup_cannot_create_unscoped_or_weak_server(self):
        for project, token, port in [
            (None, "x" * 40, 8765),
            ("demo", "short", 8765),
            ("demo", "x" * 40, 0),
        ]:
            with self.assertRaises(ContextError):
                create_app(project, token, port)
        with self.assertRaises(ContextError):
            create_app("demo", "x" * 40, 8765, read_only=False)

    def test_rejects_auth_host_origin_and_oversize_before_sdk_or_store(self):
        app = create_app("not-a-real-project", "x" * 40, 8765)
        self.assertTrue(callable(app))

        async def request(headers):
            messages = []

            async def receive():
                raise AssertionError("rejected request must not read body")

            async def send(message):
                messages.append(message)

            await app(
                {"type": "http", "method": "POST", "path": "/mcp", "headers": headers},
                receive,
                send,
            )
            return next(
                message["status"]
                for message in messages
                if message["type"] == "http.response.start"
            )

        base = [(b"host", b"127.0.0.1:8765")]
        auth = [(b"authorization", b"Bearer " + b"x" * 40)]
        self.assertEqual(asyncio.run(request(base)), 401)
        self.assertEqual(asyncio.run(request([(b"host", b"evil.invalid"), *auth])), 403)
        self.assertEqual(
            asyncio.run(request([*base, *auth, (b"origin", b"https://evil.invalid")])),
            403,
        )
        self.assertEqual(
            asyncio.run(request([*base, *auth, (b"content-length", b"9999999")])), 413
        )
