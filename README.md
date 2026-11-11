# Gate for Hermes

Shared project knowledge and assigned tasks in Hermes. Gate context and tools are
available in your sessions. Your Hermes gateway picks up tasks assigned to your
agent and records verified results or blockers in Gate when work completes.
Connection and task execution depend on valid credentials, a running gateway and
your configured model/provider.

## Connect

Get your **Gate URL** and a dedicated **agent token** from your Gate administrator.
Install and enable this plugin using Hermes's plugin installer. It prompts for
both values and saves them in the selected profile. The token field is masked.

Install the public plugin:

```sh
hermes plugins install https://github.com/Ni-Agent/hermes-gate-plugin.git
```

Release packages are available on the [releases page](https://github.com/Ni-Agent/hermes-gate-plugin/releases).
For an existing local source checkout instead:

```sh
hermes plugins install file:///absolute/path/to/hermes-gate-plugin
```

For a supplied Git bundle, clone it to a local repository first:

```sh
git clone /absolute/path/to/hermes-gate-0.1.0-beta.1.bundle "$HOME/hermes-gate-plugin"
hermes plugins install "file://$HOME/hermes-gate-plugin"
```

Then activate the gateway:

- First setup: `hermes gateway setup`
- Configured gateway stopped: `hermes gateway start`
- Gateway already running: `hermes gateway restart`

Run `hermes gate status` to verify the authenticated identity and task pickup.

Requires Linux, Python 3.11+, and Hermes Agent v0.23.0. Tested against stable
commit `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`. Your Hermes model/provider must
already be configured. Existing sessions should be restarted to load new tools.

## Use

Ask Hermes to read a project from Gate. You can also use `gate_read`, `gate_write`
and `gate_status` directly. Assign a task to the identity reported by
`hermes gate status`, with status `open` or `ready`. Keep the gateway running to
receive assignments. The task will show its progress and outcome in Gate.
For a first note, ask Hermes:

> Use gate_write to create /kb/projects/getting-started with Markdown "# Getting
> started" and a short description of this project. Use a fresh operation ID and
> create-only ETag *. Then read it back with gate_read and confirm the saved text.

For an assigned-task example and result inspection, see Same-machine setup below.

Tasks use the selected profile's tools, credentials and approval settings. Work
needing an interactive approval may need your attention. Review results before
relying on changes to other systems.

By default, task files go under the profile's `gate-work` directory. To choose a
workspace or task time limit, add these settings to Hermes config.yaml, preserving
your other configuration:

```yaml
plugins:
  enabled: [gate]
  entries:
    gate:
      settings:
        workspace: /home/hermes/work
        worker_timeout: 1800
```

If your profile restricts toolsets, include `gate`. To stop automatic pickup while
retaining the Gate tools, disable its gateway platform:

```yaml
gateway:
  platforms:
    gate:
      enabled: false
```

Then restart the gateway. Closing a chat does not stop task pickup.

## Status and recovery

`hermes gate status` shows the authenticated identity, server version, connection
and local tasks needing action or execution. Completed local bookkeeping is hidden.
Use `hermes gate status --json` for machine-readable status and full local history. For gateway logs, use `hermes logs gateway --follow`. Private
worker logs stay in the profile's `plugin-data` directory; status gives the exact
run ID and log path for active work and tasks needing review.

An interrupted task can require review. Inspect its Gate record, worker log and
any changes already made. After deciding that resuming is safe:

```sh
hermes gateway stop
hermes gate resume TASK_ID
hermes gateway start
```

Resuming starts a new session for the same task run. Previous actions are not
undone, and previous conversation transcripts are not restored automatically.

If status reports missing/invalid configuration, check `GATE_URL` and `GATE_TOKEN`
in the selected Hermes profile's `.env`. Authentication rejection means the token
needs correction or replacement by the Gate operator. Connection unavailable means
Gate may be stopped or the URL is wrong. After correcting the values, restart the
Hermes gateway and run status again. A reachable server with pickup disabled still
allows manual tools; enable `gateway.platforms.gate.enabled` to receive tasks.

## Upgrade an existing installation

Keep the existing profile and credentials. Stop the previous `hermes gate listen`
process before updating. If you enabled a separate Gate user service, stop and
disable it once:

```sh
systemctl --user disable --now hermes-gate.service
```

Run `hermes plugins update gate` for an existing Git installation, or reinstall
from the supplied source. Restart the Hermes gateway afterward. Existing tasks and
reconnect state are retained. Current releases use the Hermes gateway.
Do not delete the plugin's data directory during the upgrade.

## Same-machine setup

Run Gate and Hermes on the same Linux machine. Download a matching Linux archive
from [Gate releases](https://github.com/Ni-Agent/gate/releases) and follow the
[native setup guide](https://github.com/Ni-Agent/gate/blob/main/SETUP.md) with `http://127.0.0.1:18084` as the public URL. Keep Gate bound
to `127.0.0.1:18084`. The `gate-local setup` command creates the dedicated `agent:hermes` token at
`~/.local/share/gate/config/hermes.token` by default (or
`$GATE_HOME/config/hermes.token` for a custom instance). Use that existing token;
do not run token creation again. In a private terminal, read the default file with
`cat ~/.local/share/gate/config/hermes.token`, then enter it in the masked installer
prompt. Install the plugin using the Connect instructions above. Enter `http://127.0.0.1:18084`
and the dedicated token into the installer's masked token prompt. Keep the token
out of chats, shell command arguments and repositories. HTTPS is required for a
remote host; cleartext HTTP is accepted only for literal loopback addresses.
Redirects are rejected.

Start the Hermes gateway and run `hermes gate status`. Once task pickup is
connected, open a Hermes chat and ask:

> Use gate_status to get my identity. Use gate_write to create a task with title
> "First Gate task", project "getting-started", description "Write one short joke
> in the task result", responsible set to that identity and status "ready".
> Tell me the returned task ID.

Leave the gateway running. Ask Hermes `Use gate_read to read /tasks/TASK_ID and
show its status and saved result`, substituting the returned ID. Confirm that Gate
records the result and terminal status. A claimed task alone is not evidence of completion.
If a worker exits without a confirmed result, status shows it as needing review.

Current Gate identities have equal data access. Use a dedicated test Gate
instance for evaluation. Token administration uses the host's existing access;
ChatGPT OAuth is separate from the Hermes agent token.

Developer design notes and validation are in [the gateway ADR](docs/adr/0001-gateway-owned-task-runtime.md).
MIT license.
