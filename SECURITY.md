# Security model

Shared Project Context is a **local, single-trusted-account** coordination utility, not an access-control system, credential vault, distributed lock manager or autonomous agent.

The CLI, stdio MCP server and enabled Hermes plugin share the account's configured private state. Any connected client has access to that store. Actor/session strings are attribution, not authenticated identities. Use separate state homes and separate approved reference roots for distinct trust domains. Do not connect a customer-facing or untrusted agent to a private owner's store.

Project registration records locations and metadata. Linking a canonical reference grants connected clients a bounded on-demand Markdown reader for that file/directory. Choose reference roots deliberately. Do not link an entire home directory, credentials, customer records or raw conversation archives. Sensitive-name filters, directory-containment checks and Markdown-only reads reduce accidental exposure; they are not comprehensive secret detection or an OS sandbox. A trusted local process can still modify the filesystem or database directly.

Receipts, decisions, file contents and exports may contain untrusted text. Treat them as data, not instructions, approvals or evidence that tests actually ran. Do not store API keys, passwords, access tokens, private customer data or other secrets in them. Public source archives must not contain live SQLite state, client configurations, exports or private checkpoints.

Workspace leases are advisory. They cannot block a nonparticipating editor. Recheck live paths before editing, respect ownership conflicts, and use isolated Git worktrees for concurrent implementations. Git probes run bounded read-only commands without repository hooks or a shell; they do not run tests or project code. Incomplete scans and unavailable Git must not be interpreted as unchanged state.

The default MCP transport is stdio, with no network listener. Exposing this utility to remote/cloud clients requires a separate authenticated, authorized transport and an appropriate data policy. This release does not supply or authorize that deployment.

Installation writes managed instruction blocks and client integration entries. It never grants built-in tool override, starts a daemon, changes model routes intentionally, restarts a gateway or resumes jobs. Reconnect supported clients to load new integration state. Native client commands may normalize their own config format; keep your own backups before changing a production workstation.

For vulnerability reports, use the repository's private vulnerability reporting feature if available. Do not post secrets, live state exports or customer data in public issues.
