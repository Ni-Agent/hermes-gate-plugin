# Gate for Hermes

Shared project knowledge and assigned tasks in Hermes. Gate context and tools are
available in your sessions. Your Hermes gateway picks up tasks assigned to your
agent and records their results in Gate.

## Connect

Get your **Gate URL** and a dedicated **agent token** from your Gate administrator.
Install and enable this plugin using Hermes's plugin installer. It prompts for
both values and saves them in the selected profile. The token field is masked.

For a source checkout:

```sh
hermes plugins install file:///absolute/path/to/hermes-gate-plugin
hermes gateway restart
hermes gate status
```

For a supplied Git bundle, clone it to a local repository first:

```sh
git clone /absolute/path/to/hermes-gate-0.1.0-beta.2.bundle "$HOME/hermes-gate-plugin"
hermes plugins install "file://$HOME/hermes-gate-plugin"
hermes gateway restart
```

If Hermes has no gateway installed yet, run `hermes gateway setup`. Use
`hermes gateway start` to start an already configured gateway that is stopped.

Requires Linux, Python 3.11+, and Hermes Agent v0.23.0. Tested against stable
commit `2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19`. Your Hermes model/provider must
already be configured. Existing sessions should be restarted to load new tools.

## Use

Ask Hermes to read a project from Gate. You can also use `gate_read`, `gate_write`
and `gate_status` directly. Assign a task to the identity reported by
`hermes gate status`, with status `open` or `ready`. Keep the gateway running to
receive assignments. The task will show its progress and outcome in Gate.

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
and local task outcomes. For gateway logs, use `hermes logs --follow`. Private
worker logs are stored under the profile's `plugin-data` directory.

An interrupted task can require review. Inspect its Gate record, worker log and
any changes already made. After deciding that resuming is safe:

```sh
hermes gateway stop
hermes gate resume TASK_ID
hermes gateway start
```

Resuming starts a new session for the same task run. Previous actions are not
undone, and previous conversation transcripts are not restored automatically.

## Upgrade from beta1

Keep the existing profile and credentials. Stop the previous `hermes gate listen`
process before updating. If you enabled beta1's separate user service, stop and
disable it once:

```sh
systemctl --user disable --now hermes-gate.service
```

Update/reinstall the plugin and restart the Hermes gateway. Existing tasks and
reconnect state are retained. Beta2 has no separate Gate service to register.
Do not delete the plugin's data directory during the upgrade.

## Gate administration

The Gate administrator chooses the HTTPS URL during server setup and issues a
separate token for each agent. On the Gate host:

```sh
sudo gate-admin -url https://gate.example.org \
  -identity agent:hermes-home -out /etc/gate/hermes-home.token
sudo systemctl restart gate
```

Transfer the token privately. The command prints the output file path, not the
secret. List token IDs using `sudo gate-admin -action list-tokens`. Revoke one with
`sudo gate-admin -action revoke-token -token-id ID` and restart Gate.

Current Gate identities have equal data access. Agent tokens provide access to the
KB and tasks; keep them out of chats and repositories. Administration uses the
host's existing SSH/sudo access. ChatGPT's OAuth login is separate from an agent token.

Developer design notes and validation are in [the gateway ADR](docs/adr/0001-gateway-owned-task-runtime.md).
MIT license.
