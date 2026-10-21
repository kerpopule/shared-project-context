# Project context and rooms

A room is where participants communicate. A project is the durable unit of decisions, implementation state, receipts and ownership. Neither is a replacement for the other.

## The useful relationship

A room host can attach an explicitly authorized project to a room, obtain a fresh project packet before each turn, and expose the same scoped MCP tools to participants. Work performed outside that room then becomes visible through the project's receipts and live state. A later room can continue the same project without importing the previous room's entire transcript.

Keep the host's existing membership, dispatch, cancellation and approval controls. A teamwork toggle or participant's reply is not permission to start an orchestration run. Private conversations do not become room data just because an agent has access to them.

## Implemented bridge

```python
from shared_context.rooms import RoomBinding

# This mapping must come from trusted host configuration AFTER authorization,
# not from a model's claim about which room or project it belongs to.
binding = RoomBinding(
    room="room-42",
    member="member-7",
    session="turn-12",
    project="website-refresh",
    read_only=True,
)
packet = binding.packet(since_revision=10)
```

The packet has a schema ID, exact room/member/session binding, current project context, a revision cursor and explicit non-authority flags. It contains no room transcript. Current snapshots are observations of the context server's filesystem, not a remote member's unobserved checkout.

Room/member/session identifiers are validated. Actor attribution and lease session are deterministically namespaced, so a room member cannot substitute another member's identity through a tool argument. The corresponding MCP scope denies another project, and read-only bindings deny checkpoint/begin/finish calls.

For a separately authorized writable participant:

```python
from shared_context.rooms import RoomBinding
from shared_context.mcp import respond

binding = RoomBinding("room-42", "member-7", "turn-12", "website-refresh", read_only=False)
response = respond(
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    binding.scope(),
)
```

A long-lived stdio integration can pass the scope to shared_context.mcp.serve. A host with its own transport can pass each JSON-RPC request to respond. Neither function authenticates a remote user; the host must do that before selecting the scope. Do not accept a model-supplied project/member identifier as an authorization grant.

## Entry and exit contract

1. Validate room membership and the explicit room-to-project grant. Select the workspace deliberately, including a linked worktree when appropriate. Read packet before work, not just at room creation.
2. Inject the packet as attributed data, not a replacement system identity or hidden approval. Preserve any host prompt-size cap. Too-large packets fail explicitly rather than silently dropping important decisions. A stale history cursor reports history_gap because ordinary context only contains the ten most recent receipts.
3. Let only authorized work acquire a workspace lease and write receipts through the bound scope. Optimistic revisions and idempotency keys still apply. Stop/cancel remains host-owned. A failed or interrupted turn is not automatically transformed into a completed receipt.
4. After a meaningful checkpoint, read back the project's current revision and update the host cursor. Keep the room's message sequence cursor separate from the project's revision cursor. They measure different things.

The bridge itself never launches an agent, monitors a model, imports private chats, or converts greetings into work.

## Verification boundary

The Python bridge is implemented and tested with synthetic multi-member turns, shared decisions, lease conflicts, actor spoofing rejection, denied projects, read-only writes, failed receipts, stale cursors and packet limits.

It is not wired into a shipped Co-Agent or Hermes Rooms build. Source inspection establishes that room-aware hosts can supply per-turn context and already own their conversation/dispatch controls. It does not establish that they currently call this bridge. Installing the host adapter and observing its actual model requests is a separate integration qualification step. Do not advertise native Rooms integration based on the standalone bridge tests.
