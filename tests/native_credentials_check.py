"""Hermes's real missing-credential prompt/persistence path with synthetic answers."""

import io
import os
import pathlib
import tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory(prefix="gate-credentials-") as tmp:
    os.environ["HERMES_HOME"] = tmp
    os.environ.pop("GATE_URL", None)
    os.environ.pop("GATE_TOKEN", None)
    from ruamel.yaml import YAML
    from rich.console import Console
    from hermes_cli.config import get_env_value
    from hermes_cli.plugins_cmd_install import _prompt_plugin_env_vars

    manifest = YAML(typ="safe").load(
        (pathlib.Path(__file__).resolve().parents[1] / "plugin.yaml").read_text()
    )
    captured = io.StringIO()
    console = Console(file=captured, force_terminal=False)
    with (
        patch(
            "hermes_cli.plugins_cmd_install.line_input",
            return_value="https://gate.example",
        ) as url_prompt,
        patch(
            "hermes_cli.plugins_cmd.masked_secret_prompt",
            return_value="synthetic-test-token",
        ) as token_prompt,
    ):
        _prompt_plugin_env_vars(manifest, console)
        assert url_prompt.call_count == 1
        assert token_prompt.call_count == 1
    assert get_env_value("GATE_URL") == "https://gate.example"
    assert get_env_value("GATE_TOKEN") == "synthetic-test-token"
    saved = pathlib.Path(tmp) / ".env"
    assert saved.exists() and saved.stat().st_mode & 0o077 == 0
    assert "synthetic-test-token" not in captured.getvalue()
    with (
        patch(
            "hermes_cli.plugins_cmd_install.line_input",
            side_effect=AssertionError("Existing URL prompted again"),
        ),
        patch(
            "hermes_cli.plugins_cmd.masked_secret_prompt",
            side_effect=AssertionError("Existing token prompted again"),
        ),
    ):
        _prompt_plugin_env_vars(manifest, console)
    print(
        "PASS: fresh profile prompts for URL + masked token, persists private credentials, does not echo token and reuses saved values"
    )
