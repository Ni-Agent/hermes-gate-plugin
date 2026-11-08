"""Contract check against the real Hermes checkout on PYTHONPATH. No model calls."""

import os, pathlib, shutil, tempfile

with tempfile.TemporaryDirectory(prefix="gate-native-") as tmp:
    home = pathlib.Path(tmp)
    os.environ["HERMES_HOME"] = str(home)
    os.environ["GATE_URL"] = "https://gate.example"
    os.environ["GATE_TOKEN"] = "synthetic-native-test"
    shutil.copytree(
        pathlib.Path(__file__).resolve().parents[1],
        home / "plugins/gate",
        ignore=shutil.ignore_patterns(".git", "__pycache__"),
    )
    (home / "config.yaml").write_text("plugins:\n  enabled: [gate]\n")
    from hermes_cli.plugins import PluginManager

    manager = PluginManager(str(home))
    manager.discover_and_load()
    gate = next(p for p in manager.list_plugins() if p["name"] == "gate")
    assert gate["enabled"] and not gate["error"], gate
    assert gate["tools"] == 3 and gate["hooks"] == 1, gate
    assert "gate" in manager._cli_commands
    sections = manager.render_system_prompt_sections({})
    assert any(s.id == "gate.shared-context" and "Gate" in s.content for s in sections)
    assert manager._hooks["pre_llm_call"][0](is_first_turn=False) is None
    # Registration/discovery alone never creates an SSE listener or worker inbox.
    assert not list(home.rglob("inbox.sqlite"))
    manager.unload()
    print(
        "PASS: real Hermes loader, manifest, 3 tools, permanent context, hook, CLI and unload"
    )
