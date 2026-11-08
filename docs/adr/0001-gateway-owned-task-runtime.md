# Gateway-owned Gate task runtime

2026-11-08 — implemented in 0.1.0-beta.2; actual VM acceptance pending.

## Decision and scope

Register a native Hermes gateway platform adapter from the eager standalone plugin.
The existing plugin still registers permanent Gate system context, the orientation
hook, tools, CLI status and explicit interrupted-run recovery. Configuration plus
credentials auto-enable the platform through Hermes's existing configuration pass.
An explicit `gateway.platforms.gate.enabled: false` is respected. No second service,
manual Gate listener command, custom scheduler, or automatic setup-file rewrite.

The adapter starts an owned thread from `connect()` and stops it from
`disconnect()` and plugin unload. Runtime construction, network requests and work
run off the gateway event loop. Startup reports degraded/connecting until the
receive path opens. State changes are posted back to the owning event loop and
recorded in a private observed-status file. Runtime profile lock prevents overlap
with the beta1 listener and with duplicate instances.

Keep Gate's existing authenticated outbound SSE endpoint and local SQLite inbox.
Persist accepted events with cursor, use Last-Event-ID replay and one snapshot per
connection/recovery, preserve conditional claims with durable idempotency/run IDs,
and do not periodically list tasks. Task state and results use Gate REST directly.
No `handle_message()`, chat identity, generic `send()`, or persistent project chat
is used to dispatch assignments. The required send implementation rejects chat
sends; get_chat_info supplies service metadata only. No inbound message bypass or
new trust/allowlist exemption is granted.

Task execution retains one Hermes CLI child per task with a fresh session, normal
profile approvals, ETag writes and server-managed run ownership. Hermes v0.23's CLI
can itself delegate inference to Hermes's session authority; a child process is
not a separate inference server. Profile-scoped child environment comes from
Hermes's `served_profile_child_env`, with the resolved Gate URL/token explicitly
passed to the child. Background threads inherit the owning profile context, not a
sibling profile's launch environment.

The gateway's default adapter disconnect budget is five seconds. Bound background
HTTP setup/commands to two seconds, interrupt SSE sockets, check stopping between
commands, and terminate/kill the child within the budget. A stopped/interrupted
run remains uncertain until reviewed. This does not roll back external actions or
promise exactly-once execution. Synthetic subprocess tests prove child cleanup;
actual provider/session-authority cancellation still needs VM acceptance.

## UX boundary

Installer/status output reports current outcome and actionable next steps.
Architecture rationale, old experiments and implementation history belong here or
in Gate project notes. User explicitly requested this separation. A separate
cleanup task tracks the broader public-facing copy review; beta1 is unchanged.
Beta2 updates flow-specific instructions and replaces the obsolete status tutorial
with observed gateway connection state.

## Evidence

- Native APIs verified against the user's actual stable release: Hermes Agent
  v0.23.0, commit `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`.
- Native loader and config tests cover permanent context, tools and automatic
  platform enablement. No network work starts on plugin discovery alone.
- `tests/native_gateway_check.py` exercises the actual Hermes platform registry,
  configuration and BasePlatformAdapter with a real Gate server and synthetic
  child executable: live pickup, offline replay across adapter replacement, one
  execution each, chat-send rejection, bounded shutdown of a SIGTERM-resistant
  child, uncertain-run recovery, cross-profile credential scoping and unload.
- Existing eight REST/SSE/inbox integration tests passed. Native beta1-to-beta2
  update was verified to preserve profile credentials and user-owned plugin files.

Run with a Hermes checkout/environment and built Gate executables:

```sh
GATE_TEST_BIN_DIR=/path/to/gate-binaries python3 -m unittest discover -s tests -v
PYTHONPATH=/path/to/hermes-agent python tests/native_loader_check.py
PYTHONPATH=/path/to/hermes-agent GATE_TEST_BIN_DIR=/path/to/gate-binaries python tests/native_gateway_check.py
PYTHONPATH=/path/to/hermes-agent python tests/native_install_check.py
PYTHONPATH=/path/to/hermes-agent python tests/native_upgrade_check.py
```

Public guide used as API entry point; exact stable source is authoritative:
https://hermes-agent.nousresearch.com/docs/developer-guide/adding-platform-adapters

Deferred: hosting Gate in Hermes, public admin dashboard/usage, permissions,
message delivery, more scheduling features, orphaned external-run reconciliation.
Gate server API/storage are unchanged by this plugin release.

## Beta3 startup correction

The user reported `Platform Gate requirements not met` after beta2's real gateway
restart, while the CLI authenticated successfully. Reproduced the failure against
the installed v0.23.0 source: load configuration, then enable multiplexing as
GatewayRunner does, and probe/create the primary adapter without a turn secret
scope. Beta2's plain `get_secret` raises in that context and `configured()` masks
it as a failed requirements probe. The earlier native test kept a profile scope
bound throughout and missed the transition.

Use Hermes's adapter-native `get_scoped_secret`, which retains scoped-profile
isolation and handles the unscoped launch profile. Keep the stdlib dependency
probe independent from credential validation. The regression now covers both the
scoped profile with a deliberately wrong process token and the actual unscoped
multiplex primary startup, including task execution and reconnect. No credential
rotation, server change or Hermes core update is needed.

## Acceptance and credential onboarding

On 2026-11-08 the user confirmed beta3 works on the actual Hermes VM after the
startup fix. This confirms the previously failing gateway startup; no new beta3
voice-task transcript was supplied in that confirmation. The earlier beta1
voice-created task and the automated gateway/task tests remain separate evidence.

`tests/native_credentials_check.py` exercises Hermes v0.23.0's real credential
prompt/persistence function in a fresh temporary profile with synthetic answers.
It verifies that a missing Gate URL uses the normal input prompt, the missing
token uses the masked secret prompt, the saved `.env` is private, console output
does not disclose the token, and a second invocation reuses existing values.
Run it with `PYTHONPATH=/path/to/hermes-agent python tests/native_credentials_check.py`.

The plugin's `requires_env` declarations drive native onboarding. It prompts for
credentials that the Gate administrator has already issued; it does not create an
account or issue a token. These prompts save values and do not validate remote
authentication during installation. `hermes gate status` verifies connectivity
and authentication afterward. A new installation still requires a configured
Hermes model/provider and Hermes's normal gateway setup. Broader first-user UX
review remains tracked separately from this startup fix.
