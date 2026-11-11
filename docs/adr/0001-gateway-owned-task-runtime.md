# Gateway-owned Gate task runtime

## Decision and rationale

Gate registers a native Hermes gateway platform adapter. The plugin also
registers permanent Gate context, a session orientation hook, three tools, status
and explicit interrupted-run recovery. The existing Hermes gateway owns task
pickup so its lifecycle, profile selection and credential scope apply to Gate.
Configuration and credentials enable the platform through the native configuration
pass; `gateway.platforms.gate.enabled: false` disables it.

The adapter starts a thread from `connect()` and stops it from `disconnect()` and
plugin unload. Runtime construction, network requests and task work run outside
the gateway event loop. Connection state is posted back to that loop and saved
in a private observed-status file. A profile lock prevents overlapping runtimes.
Plugin discovery alone starts no listener or worker.

## Delivery and execution

The runtime uses Gate's authenticated outbound SSE endpoint and a private SQLite
inbox. Event acceptance and replay cursor persistence share a transaction.
Last-Event-ID supports replay; one reconciliation runs on connection or recovery.
Task discovery does not periodically scan the server. Gate REST handles task
claims and results with ETags, durable operation IDs and server-managed run IDs.
A lost claim response retries the same conditional request.

Each task runs in a fresh Hermes CLI child session under the selected profile's
normal tools and approvals. The profile child environment comes from Hermes's
`served_profile_child_env`, with the resolved Gate URL/token passed explicitly.
Background threads inherit the owning profile context. Hermes may delegate model
inference to its session authority; a CLI child is not a separate inference server.
Gate tasks do not use chat destinations, persistent project chats or inbound chat
trust exceptions. The adapter's required chat-send method rejects chat delivery.

The adapter bounds background HTTP setup and commands to two seconds, interrupts
SSE sockets on shutdown, and terminates or kills the CLI child within the
five-second adapter disconnect budget. An interrupted worker or an unverifiable
terminal result becomes uncertain and requires review. This preserves visibility
of possible side effects; it does not undo actions or promise exactly-once effects.
CLI child cleanup does not by itself establish cancellation of work delegated to
an external provider or session authority.

## Credentials and operational output

Hermes's native installer prompts for an operator-issued Gate URL and a masked
dedicated agent token. It persists credentials in the selected profile. The
installer saves values; `hermes gate status` subsequently checks authentication.
A configured Hermes model/provider and the normal Hermes gateway setup are required.
HTTP is accepted only for literal loopback origins; remote origins require HTTPS.
Authenticated requests reject redirects.

Default status reports observed connectivity and local work awaiting execution or
review. Machine-readable status includes local history, run IDs and exact private
worker-log paths. Completed/skipped inbox bookkeeping is not a current server task
list. Orientation falls back to a bounded project index with complete paths and an
explicit partial-index notice. Product-facing setup and status remain focused on
current state and useful next actions.

## Regression history and validation

The native platform integration was introduced in beta2. Beta3 corrected startup
under Hermes multiplexing: a plain secret lookup fails when the primary adapter
starts outside a turn-bound profile scope. Adapter-native `get_scoped_secret`
handles that startup context while preserving profile isolation. Regression checks
cover both a scoped profile with a deliberately wrong process token and unscoped
multiplex primary startup, including task execution and reconnect.

V1 beta adds actionable status and recovery paths, bounded orientation fallback,
and preservation of uncertain execution after worker HTTP errors. A successful
child exit without a confirmed terminal Gate result remains uncertain.

The native checks target Hermes Agent v0.23.0, commit
`2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`:

- Unit and real-server integration checks cover client boundaries, SSE parsing,
  transactional inbox recovery, conditional claim retry, live pickup, replay,
  task-result uncertainty and readable bounded status/orientation.
- Native loader/config checks cover permanent context, tools and auto-enablement.
- Native gateway checks exercise the real platform registry and adapter with Gate
  and synthetic worker processes: pickup, replay, shutdown of a SIGTERM-resistant
  child, uncertainty, credential scope and unload.
- Clean-install and beta1-upgrade checks use committed Git source; upgrade retains
  credentials and user-owned files.
- Credential checks use a fresh temporary profile and synthetic answers to verify
  masked prompts, private persistence, no console disclosure and credential reuse.

Run against a Hermes checkout/environment and built Gate executables:

```sh
GATE_TEST_BIN_DIR=/path/to/gate-binaries python3 -m unittest discover -s tests -v
PYTHONPATH=/path/to/hermes-agent python tests/native_loader_check.py
PYTHONPATH=/path/to/hermes-agent GATE_TEST_BIN_DIR=/path/to/gate-binaries python tests/native_gateway_check.py
PYTHONPATH=/path/to/hermes-agent python tests/native_install_check.py
PYTHONPATH=/path/to/hermes-agent python tests/native_upgrade_check.py
PYTHONPATH=/path/to/hermes-agent python tests/native_credentials_check.py
PYTHONPATH=/path/to/hermes-agent GATE_TEST_BIN_DIR=/path/to/gate-binaries python tests/native_consumer_check.py
```

The [Hermes adapter guide](https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters)
is an API entry point; the pinned stable source defines the tested contract.
Synthetic tests verify the listed cases, not every provider's behavior or an
unattended execution guarantee for tasks requiring interactive approval.
