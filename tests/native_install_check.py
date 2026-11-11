"""Optional clean-install contract test against real Hermes on PYTHONPATH. No model calls."""

import os, tempfile, pathlib

with tempfile.TemporaryDirectory(prefix="gate-install-check-") as home:
    os.environ["HERMES_HOME"] = home
    from hermes_cli.plugins_cmd_install import _install_plugin_core

    target, manifest, name = _install_plugin_core(
        pathlib.Path(__file__).resolve().parents[1].as_uri(), force=False
    )
    assert name == "gate" and (target / "plugin.yaml").is_file()
    assert manifest["version"] == "0.1.0-beta.1", manifest["version"]
    print("PASS: native Hermes installer cloned, scanned and placed", name)
