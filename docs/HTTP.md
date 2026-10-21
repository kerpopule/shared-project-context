# Optional HTTP transport

The base package remains dependency-free and uses no listener. The optional HTTP extra requires Python 3.10+ and the pinned official MCP SDK 2.3.0 plus Uvicorn 0.54.0.

```sh
python3 -m pip install 'shared-project-context[http]'
shared-context serve-http --project demo --port 8765 --token-env SHARED_CONTEXT_TOKEN
```

For an unpublished source candidate, install `.[http]` from that checkout or use its built wheel rather than assuming the public release contains this command.

The named environment variable must already hold a private, cryptographically random bearer token. The server requires 32–512 non-whitespace ASCII characters but cannot prove entropy from length. Do not put the token in a command argument, source file, chat, URL, example config, or release archive. Fixture probes generate their own disposable token and do not print it.

## Supplied boundary

The CLI binds only `127.0.0.1`, serves `/mcp`, and exposes read-only access to one explicit project. It rejects missing/wrong bearer tokens, unexpected Host/Origin values, duplicate authorization and oversized request bodies. Its scope is enforced for tools, resources and prompts. The transport is stateless and uses the official SDK's Streamable HTTP implementation.

The CLI does not offer a public bind or remote write flag. A trusted embedding can construct a writable `create_app` only with a bound actor and session, but this candidate's HTTP qualification covers read-only operation. A token identifies one trusted principal, not each person who shares that token. Do not lend an owner's token to customers or other tenants.

The HTTP request wrapper has an eight-request admission cap, a 30-second application deadline, and bounded SDK bodies. These are not an Internet-facing hardening certificate: raw header deadlines, upstream TLS, rate limiting, authenticated identity mapping, token rotation/revocation, OS isolation and fair multi-tenant scheduling still belong to a separately qualified deployment. If a write-capable embedding times out, its outcome can be unknown; keep the same core retry key rather than inventing a new action.

## Cloud connections

This is a tested transport component, not a hosted connector. A cloud client cannot reach your loopback address. An explicitly approved private route or authenticated HTTPS deployment is still required. A reverse proxy must preserve bearer authentication and deliberately rewrite the backend Host to the allowed loopback host/port. This package provisions no proxy, tunnel, account, OAuth issuer, public endpoint or background service.

Grok Bot's Command connection can instead use a previously authorized SSH route. HTTP-capable clients can use this component through an approved HTTPS host. OpenAI dots still needs an account-enabled app/plugin or a connected local computer; a passing SDK test does not prove that account workflow.

## Verification

Install the HTTP extra in an isolated environment, then run:

```sh
python3 -m unittest discover -s tests_http -v
python3 tools/verify_http.py
```

The second command opens a temporary owned loopback listener, uses the official SDK client for initialization, discovery, context, resources and prompts, exercises denial paths, and closes the listener in `finally`. On the maintainer machine it is run under a bounded process resource lease. The authentication negative control disables the actual comparison and confirms the denial test would fail. Neither command runs model inference. No cloud account, production host or shipped Rooms app is qualified by these tests.
