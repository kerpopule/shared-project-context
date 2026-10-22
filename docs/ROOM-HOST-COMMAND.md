# Owner-configured room turn command (development)

The development branch adds `shared-context room-context`. The v0.2.0 release remains unchanged. This command bridges a room host to `RoomBinding`; installing the Python package alone does not wire a shipped host.

## Explicit access, no inferred room authority

Create a local owner-private JSON file (POSIX mode `0600`), outside a repository or application bundle. Supply the absolute state directory. Each grant names a host, exact room, project, and exact member IDs. An optional workspace must be an absolute registered workspace path.

```json
{
  "version": 1,
  "state": "/absolute/private/shared-context-state",
  "rooms": [
    {"host": "coagent", "room": "room-id", "project": "project-id", "members": ["member-id"]}
  ]
}
```

The schema accepts `coagent` and `hermes` host names. Never derive this file from model output, participant prose, room names, a teamwork toggle, or a claimed authorization. Symlinked, shared-readable, oversized and malformed configurations are rejected. No automatic access to registered projects is granted. Unknown rooms produce a disabled result; unknown members of a bound room fail closed. Every packet is read-only, contains current project truth, and retains the non-authority notice.

```sh
shared-context room-context --config /absolute/private/room-grants.json \
  --host coagent --room room-id --member member-id --session host-session-id
```

Output is one JSON object with `enabled`, `context` and `scope`. Errors exit nonzero, not partial success. The context is bounded and carries attributed data, not a replacement system prompt. `scope` identifies the configured grant/state rather than the current revision, so outside updates refresh the next turn without unnecessary session changes.

## Host command contract

A host configures an absolute executable plus literal argv prefix, for example:

```json
["/absolute/private/bin/shared-context", "room-context", "--config", "/absolute/private/room-grants.json", "--host", "coagent"]
```

Before submitting a new turn the host appends `--room`, `--member` and `--session` from its authenticated local dispatch state, never from model arguments. Execute without a shell, with a five-second timeout, bounded output, and no stdin. Accept only valid JSON with boolean `enabled`, string `context`, and a 64-hex `scope` when enabled. An enabled result with no scope, or a disabled result with nonempty context, is invalid. Refuse to submit on configured-command failure.

Do not silently truncate a project packet to fit the host's prompt cap. Deny the turn and request a narrower project packet instead. Recheck the scope before restarting a stored request. A changed/removed grant must not silently resume provider history containing prior project data. Hosts may clear provider history under their ordinary session policy or fail closed and require a fresh room. Do not erase old transcripts or advertise revocation as recalling information already sent.

## Qualification limits

Synthetic cross-repository qualification has exercised both candidate host dispatch paths with real project storage and a real command subprocess, without model inference or live accounts. Candidate host source is maintained in its own repository, not embedded here. This is not proof that a shipped Co-Agent/Hermes application has been upgraded or activated.

This local host command is not a cloud connector, OAuth service, or an authorization to share local context with a Grok Bot/OpenAI dot. Those need the exact account/computer, chosen project, real connection readback, and an authorized connectivity path. The existing read-only SSH/stdio recipes avoid creating a public endpoint. Never describe a recipe, SDK fixture or Codex transport probe as a connected cloud account.
