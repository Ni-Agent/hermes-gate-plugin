"""Real Hermes registry/config/adapter lifecycle, real Gate and isolated worker processes.
Requires PYTHONPATH=Hermes source and GATE_TEST_BIN_DIR. No paid model calls.
"""

import asyncio
import json
import os
import pathlib
import shutil
import signal
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_integration import Integration
from gate_plugin import listener_status

SOURCE = pathlib.Path(__file__).resolve().parents[1]


async def eventually(fn, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("Native gateway check timed out")


async def check(fixture):
    home = fixture.root / "profile"
    home.mkdir()
    shutil.copytree(
        SOURCE,
        home / "plugins/gate",
        ignore=shutil.ignore_patterns(".git", "dist", "__pycache__"),
    )
    (home / "config.yaml").write_text("plugins:\n  enabled: [gate]\n")
    (home / ".env").write_text(
        "GATE_URL=" + fixture.url + "\nGATE_TOKEN=" + fixture.token + "\n"
    )
    os.chmod(home / ".env", 0o600)
    os.environ.update(
        HERMES_HOME=str(home), GATE_URL=fixture.url, GATE_TOKEN=fixture.token
    )
    fakebin = fixture.root / "bin"
    fakebin.mkdir()
    worker = fakebin / "hermes"
    worker.write_text(
        """#!/usr/bin/env python3
import json,os,pathlib,signal,sys,time,uuid
sys.path.insert(0, """
        + repr(str(SOURCE))
        + """)
from gate_plugin import Client
home=pathlib.Path(os.environ['HERMES_HOME'])
client=Client(os.environ['GATE_URL'],os.environ['GATE_TOKEN'])
tid=os.environ['GATE_WORKER_TASK_ID'];run=os.environ['GATE_WORKER_RUN_ID']
assert sys.argv[1:3]==['chat','-q'] and sys.argv[-1]=='--quiet'
assert 'Synthetic' in client.request('/kb/projects/test')['body']
with (home/'executions').open('a') as f:f.write(tid+' '+run+'\\n')
(home/'worker.pid').write_text(str(os.getpid()))
task,etag=client.task(tid)
if task['title']=='Slow worker':
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 (home/'slow.ready').write_text('ready')
 time.sleep(60)
else:
 body={k:task.get(k,'') for k in ['project','title','description','responsible','status']}
 body['status']='done';body['description']='Native gateway isolated-process test completed'
 client.request('/tasks/'+tid,'PUT',json.dumps(body),etag,uuid.uuid4().hex)
"""
    )
    worker.chmod(0o700)
    os.environ["PATH"] = str(fakebin) + os.pathsep + os.environ["PATH"]
    from agent.secret_scope import (
        set_secret_scope,
        reset_secret_scope,
        set_multiplex_active,
    )

    scope = set_secret_scope(
        {"GATE_URL": fixture.url, "GATE_TOKEN": fixture.token}, profile_home=str(home)
    )
    os.environ["GATE_TOKEN"] = "another-profile-token"
    from hermes_cli.plugins import get_plugin_manager
    from gateway.config import load_gateway_config, Platform
    from gateway.platform_registry import platform_registry

    manager = get_plugin_manager()
    manager.discover_and_load()
    gate = next(p for p in manager.list_plugins() if p["name"] == "gate")
    assert gate["enabled"] and not gate["error"], gate
    (home / "config.yaml").write_text(
        "plugins:\n  enabled: [gate]\ngateway:\n  platforms:\n    gate:\n      enabled: false\n"
    )
    disabled = load_gateway_config()
    assert not disabled.platforms[
        Platform("gate")
    ].enabled, "Explicit disable was ignored"
    (home / "config.yaml").write_text("plugins:\n  enabled: [gate]\n")
    config = load_gateway_config()
    platform = Platform("gate")
    assert config.platforms[
        platform
    ].enabled, "Gate did not auto-enable from installed credentials"
    assert (
        platform in config.get_connected_platforms()
    ), "Gate was not accepted as configured"
    created = []
    try:
        adapter = platform_registry.create_adapter("gate", config.platforms[platform])
        assert adapter is not None
        created.append(adapter)
        adapter.set_message_handler(
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("Task entered chat pipeline")
            )
        )
        begin = time.monotonic()
        assert await adapter.connect()
        assert time.monotonic() - begin < 0.2, "connect blocked the gateway loop"
        await eventually(
            lambda: adapter._runtime is not None and adapter._runtime.connected
        )
        await eventually(
            lambda: listener_status(adapter._directory)["state"] == "connected"
        )
        first = await asyncio.to_thread(fixture.create, "Gateway task")
        await eventually(
            lambda: adapter._runtime.inbox.row(first)
            and adapter._runtime.inbox.row(first)[0] == "done"
        )
        assert (await adapter.send("ignored", "ignored")).success is False
        directory = adapter._directory
        await adapter.disconnect()
        assert not adapter._thread.is_alive()
        assert listener_status(adapter._directory)["state"] == "stopped"
        # GatewayRunner enables multiplexing after loading configuration. Its primary
        # adapter is then probed without a turn/profile scope: mirror that transition.
        reset_secret_scope(scope)
        scope = None
        os.environ["GATE_TOKEN"] = fixture.token
        set_multiplex_active(True)
        offline = await asyncio.to_thread(fixture.create, "Offline gateway task")
        adapter2 = platform_registry.create_adapter("gate", config.platforms[platform])
        created.append(adapter2)
        assert await adapter2.connect()
        await eventually(
            lambda: adapter2._runtime is not None
            and adapter2._runtime.inbox.row(offline)
            and adapter2._runtime.inbox.row(offline)[0] == "done"
        )
        lines = (home / "executions").read_text().splitlines()
        assert sum(line.startswith(first + " ") for line in lines) == 1
        assert sum(line.startswith(offline + " ") for line in lines) == 1
        slow = await asyncio.to_thread(fixture.create, "Slow worker")
        await eventually(lambda: (home / "slow.ready").exists())
        pid = int((home / "worker.pid").read_text())
        begin = time.monotonic()
        await adapter2.disconnect()
        assert (
            time.monotonic() - begin < 4.5
        ), "disconnect exceeded Hermes 5-second budget"
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError("Worker process survived gateway shutdown")
        adapter3 = platform_registry.create_adapter("gate", config.platforms[platform])
        created.append(adapter3)
        assert await adapter3.connect()
        await eventually(
            lambda: adapter3._runtime is not None and adapter3._runtime.connected
        )
        assert adapter3._runtime.inbox.row(slow)[0] == "uncertain"
        assert (
            sum(
                line.startswith(slow + " ")
                for line in (home / "executions").read_text().splitlines()
            )
            == 1
        )
        # Unloading the native plugin also stops its adapter-owned runtime.
        manager.unload()
        await eventually(lambda: not adapter3._thread.is_alive())
        assert not adapter3.is_connected
        assert platform_registry.get("gate") is None
        assert all(
            not x.is_alive()
            for x in [adapter._thread, adapter2._thread, adapter3._thread]
        )
        print(
            "PASS: exact Hermes config auto-enable, native adapter lifecycle, independent workers, replay, bounded shutdown, uncertain recovery and unload"
        )
    finally:
        for adapter in created:
            await adapter.disconnect()
        manager.unload()
        if scope is not None:
            reset_secret_scope(scope)
        set_multiplex_active(False)


if __name__ == "__main__":
    fixture = Integration("test_no_idle_task_polling")
    fixture.setUp()
    try:
        asyncio.run(check(fixture))
    finally:
        fixture.tearDown()
