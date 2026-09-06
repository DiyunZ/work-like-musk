import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


CLI = Path(__file__).resolve().parents[1] / "skills/work-like-musk/scripts/five_step.py"
IDS = ["question", "delete", "simplify", "accelerate", "automate"]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project with spaces $(touch NEVER) `whoami`"
        self.project.mkdir()
        self.task = "task-a"
        self.state_path = self.path_for(self.project, self.task)

    def path_for(self, project, task):
        return project / ".work-like-musk/sessions" / (hashlib.sha256(task.encode()).hexdigest() + ".json")

    def invoke(self, command, *args, project=None, task=None, env=None):
        return subprocess.run([sys.executable, str(CLI), command, "--project", str(project or self.project),
                               "--task", task or self.task, *args], capture_output=True, text=True, env=env)

    def setup(self, **kwargs):
        result = self.invoke("setup", "--title", "A real task", "--no-open", **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def state(self):
        return json.loads(self.state_path.read_text())

    def update(self, stage, status, reason="Evidence supports this change"):
        revision = self.state()["revision"] if self.state_path.exists() else 1
        return self.invoke("update", "--stage", stage, "--status", status, "--reason", reason,
                           "--expected-revision", str(revision))

    def ok_update(self, *args):
        result = self.update(*args)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_is_idempotent_and_show_round_trips(self):
        self.setup()
        before = self.state_path.read_bytes()
        self.assertEqual([s["id"] for s in self.state()["stages"]], IDS)
        self.assertIsNone(self.state()["currentStage"])
        self.setup()
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(json.loads(self.invoke("show").stdout), self.state())
        self.ok_update("question", "in_progress")
        before = self.state_path.read_bytes()
        self.setup()
        self.ok_update("question", "in_progress")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_project_and_task_isolation(self):
        self.setup()
        self.setup(task="task-b")
        other = Path(self.temp.name) / "other"
        other.mkdir()
        self.setup(project=other)
        self.ok_update("question", "in_progress")
        for project, task in [(self.project, "task-b"), (other, self.task)]:
            state = json.loads(self.path_for(project, task).read_text())
            self.assertEqual(state["revision"], 1)
            self.assertIsNone(state["currentStage"])

    def test_task_environment_and_canonical_project(self):
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        env = dict(os.environ, CODEX_THREAD_ID=self.task)
        result = subprocess.run([sys.executable, str(CLI), "setup", "--project", str(alias), "--no-open"],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["projectPath"], str(self.project.resolve()))

    def test_runtime_directory_symlink_cannot_escape_project(self):
        shared = Path(self.temp.name) / "shared runtime data"
        shared.mkdir()
        (self.project / ".work-like-musk").symlink_to(shared, target_is_directory=True)

        result = self.invoke("setup", "--no-open")

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(list(shared.iterdir()), [], "Rejected setup must not create files outside the project")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO regression requires POSIX")
    def test_non_regular_runtime_files_fail_without_blocking(self):
        self.setup()
        valid = self.state_path.read_bytes()
        for target, command, arguments in [
            (self.state_path, "setup", ["--no-open"]),
            (self.state_path.with_suffix(".skip.json"), "request-skip",
             ["--stage", "question", "--to", "delete", "--reason", "Review the order first",
              "--expected-revision", "1"]),
        ]:
            with self.subTest(target=target.name):
                if target.exists():
                    target.unlink()
                os.mkfifo(target)
                try:
                    result = subprocess.run(
                        [sys.executable, str(CLI), command, "--project", str(self.project),
                         "--task", self.task, *arguments],
                        capture_output=True, text=True, timeout=2)
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertIn("regular file", result.stderr)
                finally:
                    target.unlink()
                    self.state_path.write_bytes(valid)

    def test_invalid_order_and_completion_leave_file_unchanged(self):
        self.setup()
        before = self.state_path.read_bytes()
        for stage, status in [("simplify", "in_progress"), ("question", "completed"), ("delete", "skipped")]:
            result = self.update(stage, status)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(self.state_path.read_bytes(), before)

    def test_direct_skip_requires_a_recorded_reminder_and_confirmation(self):
        self.setup()
        self.ok_update("question", "in_progress")
        self.ok_update("question", "completed")
        before = self.state_path.read_bytes()
        result = self.update("delete", "skipped", "The user asked to go directly to simplify")
        self.assertEqual(result.returncode, 2)
        self.assertIn("request-skip", result.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_skip_request_waits_for_confirmation_then_allows_target(self):
        self.setup()
        self.ok_update("question", "in_progress")
        self.ok_update("question", "completed")
        before = self.state_path.read_bytes()
        revision = str(self.state()["revision"])
        request = self.invoke("request-skip", "--stage", "delete", "--to", "simplify",
                              "--reason", "Deleting first avoids optimizing unnecessary work; confirm skipping?",
                              "--expected-revision", revision)
        self.assertEqual(request.returncode, 0, request.stderr)
        request_id = json.loads(request.stdout)["skipRequest"]["requestId"]
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(self.update("simplify", "in_progress").returncode, 2)
        result = self.invoke("confirm-skip", "--request-id", request_id, "--expected-revision", revision,
                             "--reason", "User confirmed skipping Delete after the ordering reminder")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["stages"][1]["status"], "skipped")
        self.assertEqual(self.state()["stages"][2]["status"], "pending")
        self.ok_update("simplify", "in_progress")
        self.ok_update("delete", "in_progress", "User chose to revisit deletion")
        self.assertTrue(all(s["status"] == "pending" for s in self.state()["stages"][2:]))
        before = self.state_path.read_bytes()
        retry = self.invoke("confirm-skip", "--request-id", request_id,
                            "--expected-revision", str(self.state()["revision"]), "--reason", "Old confirmation")
        self.assertEqual(retry.returncode, 2)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_late_report_cannot_override_reopened_work(self):
        self.setup()
        self.ok_update("question", "in_progress", "Initial requirements")
        old_revision = self.state()["revision"]
        self.ok_update("question", "in_progress", "User changed the requirements")
        before = self.state_path.read_bytes()
        result = self.invoke("update", "--stage", "question", "--status", "completed",
                             "--reason", "Old work finished", "--expected-revision", str(old_revision))
        self.assertEqual(result.returncode, 2)
        self.assertIn("revision changed", result.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_skip_request_is_idempotent_and_cannot_cross_tasks(self):
        self.setup()
        arguments = ("--stage", "question", "--to", "simplify", "--reason", "Confirm bypassing requirements and deletion?",
                     "--expected-revision", "1")
        first = self.invoke("request-skip", *arguments)
        second = self.invoke("request-skip", *arguments)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        request_id = json.loads(first.stdout)["skipRequest"]["requestId"]
        self.setup(task="task-b")
        foreign = self.path_for(self.project, "task-b").with_suffix(".skip.json")
        foreign.write_bytes(self.state_path.with_suffix(".skip.json").read_bytes())
        before = self.path_for(self.project, "task-b").read_bytes()
        result = self.invoke("confirm-skip", "--request-id", request_id, "--expected-revision", "1",
                             "--reason", "Confirmation for another task", task="task-b")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.path_for(self.project, "task-b").read_bytes(), before)
        result = self.invoke("confirm-skip", "--request-id", request_id, "--expected-revision", "1",
                             "--reason", "User explicitly confirmed bypassing both steps after the reminder")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s["status"] for s in self.state()["stages"]],
                         ["skipped", "skipped", "pending", "pending", "pending"])

    def test_invalid_skip_request_is_preserved(self):
        self.setup()
        request_path = self.state_path.with_suffix(".skip.json")
        request_path.write_text("{broken")
        result = self.invoke("request-skip", "--stage", "question", "--to", "delete",
                             "--reason", "Consider requirements before deletion", "--expected-revision", "1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(request_path.read_text(), "{broken")
        self.assertEqual(self.state()["revision"], 1)

    def test_mutation_requires_an_expected_revision(self):
        self.setup()
        before = self.state_path.read_bytes()
        result = self.invoke("update", "--stage", "question", "--status", "in_progress", "--reason", "Begin")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_block_resume_skip_and_reopen_reset_later_claims(self):
        self.setup()
        self.ok_update("question", "blocked", "Required input is missing")
        self.ok_update("question", "in_progress", "Input received")
        self.ok_update("question", "completed", "Constraints checked")
        request = self.invoke("request-skip", "--stage", "delete", "--to", "simplify",
                              "--reason", "Delete first avoids unnecessary optimization",
                              "--expected-revision", str(self.state()["revision"]))
        self.assertEqual(request.returncode, 0, request.stderr)
        confirmation = self.invoke("confirm-skip", "--request-id", json.loads(request.stdout)["skipRequest"]["requestId"],
                                   "--expected-revision", str(self.state()["revision"]),
                                   "--reason", "User confirmed no removable scope after the reminder")
        self.assertEqual(confirmation.returncode, 0, confirmation.stderr)
        self.ok_update("simplify", "in_progress")
        self.ok_update("simplify", "completed")
        self.ok_update("question", "in_progress", "Requirement changed")
        state = self.state()
        self.assertEqual(state["currentStage"], "question")
        self.assertTrue(all(s["status"] == "pending" and s["reason"] == "" and s["updatedAt"] is None
                            for s in state["stages"][1:]))

    def test_missing_and_invalid_input_do_not_create_session(self):
        result = self.update("question", "in_progress")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.state_path.exists())
        for title in [" ", "x" * 121]:
            result = self.invoke("setup", "--title", title, "--no-open")
            self.assertEqual(result.returncode, 2)
        self.setup()
        before = self.state_path.read_bytes()
        for reason in [" ", " padded ", "x" * 301]:
            self.assertEqual(self.update("question", "in_progress", reason).returncode, 2)
            self.assertEqual(self.state_path.read_bytes(), before)

    def test_root_timestamp_must_match_current_stage(self):
        self.setup()
        self.ok_update("question", "in_progress", "Checking requirements")
        wrong = self.state()
        wrong["updatedAt"] = "2000-01-01T00:00:00.000Z"
        self.state_path.write_text(json.dumps(wrong))

        result = self.invoke("show")

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(json.loads(self.state_path.read_text()), wrong)

    def test_transition_remains_valid_after_wall_clock_rollback(self):
        self.setup()
        spec = importlib.util.spec_from_file_location("five_step_rollback_test", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch.object(module, "timestamp", side_effect=[
            "2026-09-06T02:00:09.000Z",
            "2026-09-06T02:00:10.000Z",
            "2026-09-06T02:00:05.000Z",
        ]):
            state = module.transition(self.state(), "question", "in_progress", "Checking requirements")
            state = module.transition(state, "question", "completed", "Requirements checked")
            state = module.transition(state, "delete", "in_progress", "Reviewing removable scope")

        self.assertEqual(module.validate(state, self.project.resolve(), self.task), state)
        self.assertGreater(state["stages"][0]["updatedAt"], state["updatedAt"])
        self.assertEqual(state["stages"][1]["updatedAt"], state["updatedAt"])

    def test_malformed_oversized_and_foreign_state_not_replaced(self):
        self.setup()
        valid = self.state()
        invalid = [b"{bad", b" " * 65537]
        for key, value in [("taskId", "foreign"), ("schemaVersion", True), ("revision", 0),
                           ("updatedAt", "2026-02-31T00:00:00.000Z"), ("currentStage", "question")]:
            wrong = dict(valid, **{key: value})
            invalid.append(json.dumps(wrong).encode())
        wrong = json.loads(json.dumps(valid))
        wrong["stages"][1].update(status="in_progress", reason="Invalid ordering", updatedAt=valid["updatedAt"])
        wrong["currentStage"] = "delete"
        invalid.append(json.dumps(wrong).encode())
        for content in invalid:
            self.state_path.write_bytes(content)
            for command in ["setup", "show"]:
                args = ["--no-open"] if command == "setup" else []
                self.assertEqual(self.invoke(command, *args).returncode, 2)
                self.assertEqual(self.state_path.read_bytes(), content)

    def test_concurrent_duplicate_writes_are_atomic_and_idempotent(self):
        self.setup()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.update("question", "in_progress", "Concurrent report"), range(16)))
        self.assertTrue(all(r.returncode == 0 for r in results), [r.stderr for r in results])
        self.assertEqual(self.state()["revision"], 2)
        self.assertEqual(list(self.state_path.parent.glob("*.tmp")), [])

    def test_concurrent_conflicting_reports_preserve_one_winner(self):
        self.setup()
        def report(index):
            return self.invoke("update", "--stage", "question", "--status", "in_progress",
                               "--expected-revision", "1", "--reason", f"Independent report {index}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(report, range(8)))
        self.assertEqual(sum(result.returncode == 0 for result in results), 1)
        self.assertTrue(all(result.returncode in (0, 2) for result in results))
        self.assertEqual(self.state()["revision"], 2)
        self.assertEqual(list(self.state_path.parent.glob("*.tmp")), [])

    def test_duplicate_terminal_report_after_advancement_preserves_state(self):
        self.setup()
        self.ok_update("question", "in_progress", "Checking constraints")
        self.ok_update("question", "completed", "Constraints checked")
        self.ok_update("delete", "in_progress", "Reviewing removable scope")
        before = self.state_path.read_bytes()
        before_state = self.state()

        result = self.update("question", "completed", "Constraints checked")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)
        after = self.state()
        self.assertEqual(after["currentStage"], "delete")
        self.assertEqual(after["revision"], before_state["revision"])
        self.assertEqual(after["updatedAt"], before_state["updatedAt"])
        self.assertEqual(after["stages"][0]["updatedAt"], before_state["stages"][0]["updatedAt"])

    def test_open_hud_launches_in_background_with_literal_arguments(self):
        root = Path(self.temp.name) / "HUD root $(touch NEVER) `whoami`"
        executable = root / "dist/FiveStepHUD.app/Contents/MacOS/FiveStepHUD"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture executable")
        state_path = self.project / "state $HOME $(touch NEVER) `whoami`.json"
        spec = importlib.util.spec_from_file_location("five_step_open_test", CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        completed = subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(module, "__file__", str(root / "cli/five_step.py")):
            with mock.patch.object(module.subprocess, "run", return_value=completed) as run:
                module.open_hud(state_path)

        run.assert_called_once_with(
            ["/usr/bin/open", "-g", "-a", str((root / "dist/FiveStepHUD.app").resolve()), str(state_path)],
            capture_output=True,
            text=True,
        )
        self.assertFalse((self.project / "NEVER").exists())

    def test_shell_metacharacters_remain_literal(self):
        self.setup()
        reason = "Keep $HOME and $(touch NEVER) and `whoami` literal"
        self.ok_update("question", "in_progress", reason)
        self.assertEqual(self.state()["stages"][0]["reason"], reason)
        self.assertFalse((self.project / "NEVER").exists())


if __name__ == "__main__":
    unittest.main()
