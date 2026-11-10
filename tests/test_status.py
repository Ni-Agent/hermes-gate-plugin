import importlib.util, pathlib, sys, unittest

root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate_status_tests", root / "__init__.py", submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class StatusTests(unittest.TestCase):
    def test_actionable_status_hides_bookkeeping(self):
        report = {"identity": "agent:review", "server_version": "test", "url": "http://127.0.0.1:18084", "listener": {"state": "connected"}, "inbox": [
            {"task_id": "old-completed", "stage": "done"},
            {"task_id": "old-skipped", "stage": "skipped"},
            {"task_id": "review-this", "stage": "uncertain"}]}
        output = module.format_status(report)
        self.assertIn("Task pickup: connected", output)
        self.assertIn("review-this: needs review", output)
        self.assertNotIn("old-", output)

    def test_auth_failure_is_actionable_without_raw_response(self):
        output = module.format_status({"status": 401, "error": "private server response"})
        self.assertIn("Authentication rejected", output)
        self.assertNotIn("private server response", output)
