"""Real Gate process, real HTTP/SSE, fake worker (no paid model calls).
Run with GATE_TEST_BIN_DIR pointing to built gate/gate-init/gate-admin binaries.
"""

import contextlib, json, os, pathlib, socket, subprocess, sys, tempfile, threading, time, unittest, uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gate_plugin import Client, GateError, Runtime, frames

BIN = os.environ.get("GATE_TEST_BIN_DIR")


def wait_for(fn, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if fn():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for integration state")


@unittest.skipUnless(BIN, "Set GATE_TEST_BIN_DIR for real server integration tests")
class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.server = None
        self.runtimes = []
        subprocess.run(
            [
                BIN + "/gate-init",
                "-config",
                str(self.root / "config"),
                "-data",
                str(self.root / "data"),
                "-public-url",
                "https://gate.example",
            ],
            check=True,
            capture_output=True,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.url = "http://127.0.0.1:" + str(self.port)
        self.operator = Client(
            self.url, (self.root / "config/operator.token").read_text().strip()
        )
        self.start_server()
        result = subprocess.run(
            [
                BIN + "/gate-admin",
                "-url",
                self.url,
                "-operator-token-file",
                str(self.root / "config/operator.token"),
                "-tokens",
                str(self.root / "config/tokens.json"),
                "-identity",
                "agent:hermes-test",
                "-out",
                str(self.root / "hermes.token"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.token = (self.root / "hermes.token").read_text().strip()
        self.assertNotIn(self.token, result.stdout)
        self.stop_server()
        self.start_server()
        self.client = Client(self.url, self.token)
        self.executions = []
        self.operator.request(
            "/kb/projects/test",
            "PUT",
            "# Synthetic test project",
            "*",
            uuid.uuid4().hex,
        )

    def start_server(self):
        self.server = subprocess.Popen(
            [
                BIN + "/gate",
                "-addr",
                "127.0.0.1:" + str(self.port),
                "-public-url",
                "https://gate.example",
                "-repo",
                str(self.root / "data/workspace.git"),
                "-credentials",
                str(self.root / "config/credentials.json"),
                "-tokens",
                str(self.root / "config/tokens.json"),
                "-oauth-state",
                str(self.root / "data/auth/sessions.json"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def ready():
            if self.server.poll() is not None:
                raise AssertionError("Gate exited during startup")
            try:
                return self.operator.request("/whoami")["status"] == 200
            except Exception:
                return False

        wait_for(ready)

    def stop_server(self):
        if self.server:
            self.server.terminate()
            self.server.wait(timeout=8)
            self.server = None

    def tearDown(self):
        for rt, thread in self.runtimes:
            rt.stop()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.stop_server()
        self.tmp.cleanup()

    def create(self, title):
        return json.loads(
            self.operator.request(
                "/tasks",
                "POST",
                json.dumps(
                    {
                        "title": title,
                        "responsible": "agent:hermes-test",
                        "project": "test",
                    }
                ),
                operation_id=uuid.uuid4().hex,
            )["body"]
        )["id"]

    def finish(self, task_id, run_id):
        self.assertIn("Synthetic", self.client.request("/kb/projects/test")["body"])
        self.executions.append((task_id, run_id))
        task, etag = self.client.task(task_id)
        self.assertEqual(task["run_id"], run_id)
        body = {
            k: task.get(k, "")
            for k in ["project", "title", "description", "responsible", "status"]
        }
        body["status"] = "done"
        body["description"] = "Verified synthetic test result"
        self.client.request(
            "/tasks/" + task_id, "PUT", json.dumps(body), etag, uuid.uuid4().hex
        )
        return 0

    def listen(self, client=None):
        rt = Runtime(
            client or self.client,
            self.root / "plugin",
            self.root / "profile",
            self.root,
            launcher=self.finish,
        )
        thread = threading.Thread(target=rt.listen)
        thread.start()
        self.runtimes.append((rt, thread))
        wait_for(lambda: rt.connected)
        return rt, thread

    def test_live_pickup_offline_replay_and_single_claim(self):
        rt, thread = self.listen()
        task = self.create("Live delivery")
        wait_for(lambda: rt.inbox.row(task) and rt.inbox.row(task)[0] == "done")
        wait_for(lambda: rt.inbox.row(task)[0] == "done")
        rt.stop()
        thread.join(5)
        self.runtimes.remove((rt, thread))
        self.stop_server()
        self.start_server()
        offline = self.create("Created while disconnected")
        rt2, thread2 = self.listen()
        wait_for(lambda: rt2.inbox.row(offline) and rt2.inbox.row(offline)[0] == "done")
        self.assertEqual([x[0] for x in self.executions].count(task), 1)
        self.assertEqual([x[0] for x in self.executions].count(offline), 1)
        with self.assertRaises(RuntimeError):
            Runtime(self.client, self.root / "plugin", self.root / "profile", self.root)

    def test_lost_claim_reply_is_retried_exactly(self):
        base = self.client

        class LostReply:
            url = base.url

            def __init__(self):
                self.lost = False
                self.claims = []

            def task(self, *args):
                return base.task(*args)

            def request(self, path, *args, **kwargs):
                out = base.request(path, *args, **kwargs)
                if path.endswith("/claim"):
                    self.claims.append(args)
                    if not self.lost:
                        self.lost = True
                        raise ConnectionError("simulated lost successful response")
                return out

            def stream(self, *args):
                return base.stream(*args)

        c = LostReply()
        rt, thread = self.listen(c)
        task = self.create("Lost claim response")
        wait_for(lambda: rt.inbox.row(task) and rt.inbox.row(task)[0] == "done")
        self.assertEqual(len(c.claims), 2)
        self.assertEqual(c.claims[0], c.claims[1])
        self.assertEqual(len(self.executions), 1)

    def test_no_idle_task_polling(self):
        base = self.client
        counts = []

        class Counting:
            url = base.url

            def request(self, path, *args, **kwargs):
                counts.append(path)
                return base.request(path, *args, **kwargs)

            def task(self, *args):
                return base.task(*args)

            def stream(self, *args):
                return base.stream(*args)

        rt, thread = self.listen(Counting())
        wait_for(lambda: len([p for p in counts if p.startswith("/tasks?")]) == 1)
        time.sleep(0.4)
        self.assertEqual(len([p for p in counts if p.startswith("/tasks?")]), 1)

    def test_auth_and_revocation(self):
        with self.assertRaises(GateError):
            Client(self.url, "wrong").stream("0")
        tokens = json.loads((self.root / "config/tokens.json").read_text())
        token_id = tokens[-1]["id"]
        subprocess.run(
            [
                BIN + "/gate-admin",
                "-action",
                "revoke-token",
                "-tokens",
                str(self.root / "config/tokens.json"),
                "-token-id",
                token_id,
            ],
            check=True,
            capture_output=True,
        )
        self.stop_server()
        self.start_server()
        with self.assertRaises(GateError):
            self.client.request("/whoami")


if __name__ == "__main__":
    unittest.main()
