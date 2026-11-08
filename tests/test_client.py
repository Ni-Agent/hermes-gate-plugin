import io, json, pathlib, sys, tempfile, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gate_plugin import Client, Inbox, frames


class ClientTests(unittest.TestCase):
    def test_url_and_credential_boundaries(self):
        for url in [
            "http://example.com",
            "https://a/b",
            "https://u:p@a",
            "https://a?x=1",
        ]:
            with self.assertRaises(ValueError):
                Client(url, "token")
        c = Client("https://example.com", "token")
        for path in ["//evil/x", "https://evil/x", "/kb#secret"]:
            with self.assertRaises(ValueError):
                c.open(path)

    def test_parser_comments_multiline_and_limits(self):
        raw = b': ping\n\nid: 4\nevent: task\ndata: {"task_id":\ndata: "123"}\n\n'
        self.assertEqual(
            list(frames(io.BytesIO(raw))), [("task", "4", {"task_id": "123"})]
        )
        with self.assertRaises(ValueError):
            list(frames(io.BytesIO(b"data: " + b"x" * 65536)))

    def test_inbox_recovery_and_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "inbox.sqlite"
            task = "a" * 24
            box = Inbox(path, "test|agent:one")
            box.accept("19", [task])
            run = box.next()[2]
            box.stage(task, "running")
            box.db.close()
            box = Inbox(path, "test|agent:one")
            self.assertEqual(box.cursor(), "19")
            self.assertIsNone(box.next())
            self.assertEqual(box.status()["tasks"][0]["stage"], "uncertain")
            box.accept("20", [task])
            self.assertIsNone(box.next())
            box.resume(task)
            self.assertEqual(box.next()[2], run)
            box.db.close()
            with self.assertRaises(ValueError):
                Inbox(path, "other|agent:one")

    def test_cursor_and_queue_are_one_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = Inbox(pathlib.Path(tmp) / "inbox.sqlite", "scope")
            with self.assertRaises(ValueError):
                box.accept("7", ["b" * 24, "invalid"])
            self.assertEqual(box.cursor(), "0")
            self.assertIsNone(box.next())
            box.db.close()


if __name__ == "__main__":
    unittest.main()
