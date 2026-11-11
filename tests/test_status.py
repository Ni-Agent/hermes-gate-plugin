import importlib.util, json, pathlib, sys, tempfile, unittest

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

    def test_orientation_index_keeps_complete_paths_and_reports_partial_results(self):
        paths = ["/kb/projects/project-" + str(i) + "/" + "x" * 120 for i in range(200)]
        paths.append("/kb/projects/root")
        output = module.orientation_index(json.dumps({"items": [{"href": p} for p in paths]}))
        self.assertLessEqual(len(output), 2400)
        self.assertIn("Partial index", output)
        lines = [line[2:] for line in output.splitlines() if line.startswith("- ")]
        self.assertEqual(json.loads(lines[0]), "/kb/projects/root")
        self.assertTrue(all(json.loads(line) in paths for line in lines))
        self.assertLess(len(lines), len(paths))

    def test_recovery_reports_exact_private_log_without_changing_inbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = pathlib.Path(tmp)
            box = sys.modules["gate_status_tests.gate_plugin"].Inbox(directory / "inbox.sqlite", "test")
            task = "a" * 24
            box.accept("1", [task])
            run = box.next()[2]
            box.stage(task, "uncertain")
            rows = module.local_tasks(directory)
            self.assertEqual(rows[0]["run_id"], run)
            self.assertEqual(rows[0]["log_path"], str(directory / (run + ".log")))
            report = {"identity": "agent:test", "server_version": "test", "url": "http://127.0.0.1", "listener": {"state": "stopped"}, "inbox": rows}
            output = module.format_status(report)
            self.assertIn(run, output)
            self.assertIn(str(directory / (run + ".log")), output)
            self.assertIn("Stop the Hermes gateway", output)
            self.assertEqual(box.row(task)[0], "uncertain")
            box.db.close()

    def test_configuration_and_connection_errors_have_specific_actions(self):
        output = module.format_status({"error": "failed", "status": 0, "error_kind": "configuration"})
        self.assertIn("Configuration missing or invalid", output)
        self.assertIn("GATE_TOKEN", output)
        output = module.format_status({"error": "failed", "status": 0, "error_kind": "connection"})
        self.assertIn("Check that Gate is running", output)

    def test_disabled_pickup_does_not_claim_gateway_is_stopped(self):
        output = module.format_status({"identity": "agent:test", "server_version": "test", "url": "http://127.0.0.1", "listener": {"state": "disabled"}})
        self.assertIn("Task pickup: disabled", output)
        self.assertIn("gateway.platforms.gate.enabled", output)
        self.assertNotIn("First gateway setup", output)
