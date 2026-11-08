"""Native beta1-to-current updater check against Hermes on PYTHONPATH. No model calls."""

import os, pathlib, subprocess, tempfile

source = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gate-native-upgrade-") as tmp:
    root = pathlib.Path(tmp)
    home = root / "profile"
    home.mkdir()
    os.environ["HERMES_HOME"] = str(home)
    local = root / "source"
    subprocess.run(["git", "clone", "--quiet", str(source), str(local)], check=True)
    subprocess.run(
        ["git", "reset", "--hard", "v0.1.0-beta.1"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    from hermes_cli.plugins_cmd_install import _install_plugin_core

    target, manifest, name = _install_plugin_core(local.as_uri(), force=False)
    assert manifest["version"] == "0.1.0-beta.1"
    (home / ".env").write_text(
        "GATE_URL=https://gate.example\nGATE_TOKEN=synthetic-upgrade-token\n"
    )
    before = (home / ".env").read_bytes()
    (target / "user-settings.txt").write_text("keep me")
    subprocess.run(
        [
            "git",
            "reset",
            "--hard",
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip(),
        ],
        cwd=local,
        check=True,
        capture_output=True,
    )
    from hermes_cli.plugins_cmd_update import cmd_update

    cmd_update("gate", interactive=False)
    from ruamel.yaml import YAML

    expected = YAML(typ="safe").load((source / "plugin.yaml").read_text())["version"]
    assert (
        YAML(typ="safe").load((target / "plugin.yaml").read_text())["version"]
        == expected
    )
    assert (home / ".env").read_bytes() == before
    assert (target / "user-settings.txt").read_text() == "keep me"
    print("PASS: native beta1-to-current update preserves credentials and user files")
