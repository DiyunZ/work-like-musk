import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install.py"
SOURCE = ROOT / "skills/work-like-musk"
ORIGINAL = b"---\nname: work-like-musk\ndescription: Apply five ordered steps.\n---\n\n# Existing guidance\n\nKeep this paragraph exactly.\n"
LEGACY_SECTION = b"<!-- five-step-hud:start -->\n## Integrated Live Progress HUD\nRead [the guide](references/live-progress.md) and start the HUD.\n<!-- five-step-hud:end -->\n"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.skill = self.base / "skill"
        self.backups = self.base / "backups"

    def invoke(self, *extra):
        # -S excludes site packages: installation must work with only the standard library.
        args = [sys.executable, "-S", str(INSTALLER), "--skill", str(self.skill),
                "--backup-root", str(self.backups), "--agent", "claude-code"]
        return subprocess.run([*args, *extra], capture_output=True, text=True, encoding="utf-8", timeout=30)

    def installer_module(self):
        spec = importlib.util.spec_from_file_location("skill_installer", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def legacy_install(self):
        installer = self.installer_module()
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL + LEGACY_SECTION)
        for relative in installer.LEGACY_FILES:
            target = self.skill / relative
            if relative.endswith(".app"):
                target = target / "Contents/MacOS/FiveStepHUD"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"legacy owned artifact")
        return installer

    def snapshot(self):
        return {p.relative_to(self.skill): p.read_bytes() for p in self.skill.rglob("*") if p.is_file()}

    def test_fresh_install_needs_no_gui_or_third_party_packages(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(self.snapshot()), {Path("SKILL.md"), Path("agents/openai.yaml")})
        for relative, content in self.snapshot().items():
            self.assertEqual(content, (SOURCE / relative).read_bytes())
        self.assertEqual(json.loads(result.stdout)["removedFiles"], [])
        self.assertFalse((self.base / ".work-like-musk").exists())

    def test_each_agent_installs_to_its_personal_directory(self):
        installer = self.installer_module()
        personal = self.base / "personal"
        expected = {
            "codex": personal / ".codex/skills/work-like-musk",
            "claude-code": personal / ".claude/skills/work-like-musk",
            "cursor": personal / ".cursor/skills/work-like-musk",
            "gemini-cli": personal / ".gemini/skills/work-like-musk",
            "opencode": self.base / "xdg/opencode/skills/work-like-musk",
            "generic": personal / ".agents/skills/work-like-musk",
        }
        for agent, destination in expected.items():
            with self.subTest(agent=agent), \
                 mock.patch.object(installer.Path, "home", return_value=personal), \
                 mock.patch.dict(installer.os.environ, {"XDG_CONFIG_HOME": str(self.base / "xdg")}), \
                 mock.patch.object(installer.sys, "argv", [str(INSTALLER), "--agent", agent,
                                   "--backup-root", str(self.backups)]), \
                 mock.patch.object(installer.sys, "stdout", new_callable=io.StringIO), \
                 mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
                self.assertEqual(installer.main(), 0, installer.sys.stderr.getvalue())
            self.assertEqual((destination / "SKILL.md").read_bytes(), (SOURCE / "SKILL.md").read_bytes())

    def test_upgrade_removes_and_backs_up_all_legacy_files(self):
        installer = self.legacy_install()
        custom = self.skill / "scripts/custom.py"
        custom.write_bytes(b"custom helper")
        metadata = self.skill / "agents/openai.yaml"
        metadata.parent.mkdir()
        custom_metadata = b"policy:\n  allow_implicit_invocation: false\n"
        metadata.write_bytes(custom_metadata)
        sessions = self.skill / ".work-like-musk/sessions/task.json"
        sessions.parent.mkdir(parents=True)
        sessions.write_bytes(b"previous task evidence")
        before = self.snapshot()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = json.loads(result.stdout)
        self.assertEqual(set(installed["removedFiles"]), set(installer.LEGACY_FILES))
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertEqual(metadata.read_bytes(), custom_metadata)
        self.assertEqual(custom.read_bytes(), b"custom helper")
        self.assertEqual(sessions.read_bytes(), b"previous task evidence")
        backup = Path(installed["backupPath"])
        for relative in installer.LEGACY_FILES:
            self.assertFalse((self.skill / relative).exists(), relative)
        for relative, content in before.items():
            if relative not in (Path("scripts/custom.py"), Path(".work-like-musk/sessions/task.json")):
                self.assertEqual((backup / relative).read_bytes(), content)
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["removedFiles"], [])
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)

    def test_migration_removes_stock_hud_instructions_and_preserves_custom_text(self):
        installer = self.installer_module()
        stock = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
        for description in installer.LEGACY_DESCRIPTIONS:
            legacy = stock.replace(stock.splitlines()[2], description)
            for old, new in installer.COACHING_REPLACEMENTS.items():
                legacy = legacy.replace(new, old)
            custom = "\nUser constraint: preserve all report columns.\n"
            installed = installer.managed_entrypoint(legacy + LEGACY_SECTION.decode() + custom)
            self.assertEqual(installed, stock + custom)

    def test_upgrade_updates_stock_metadata_without_changing_policy(self):
        installer = self.legacy_install()
        stock = (SOURCE / "agents/openai.yaml").read_bytes()
        legacy = stock
        for old, new in installer.METADATA_REPLACEMENTS.items():
            legacy = legacy.replace(new.encode(), old.encode())
        policy = b"policy:\n  allow_implicit_invocation: false\n"
        target = self.skill / "agents/openai.yaml"
        target.parent.mkdir()
        target.write_bytes(legacy + policy)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), stock + policy)

    def test_legacy_skill_keeps_its_name_and_invocation(self):
        self.legacy_install()
        original = ORIGINAL.replace(b"work-like-musk", b"musk-five-step")
        (self.skill / "SKILL.md").write_bytes(original + LEGACY_SECTION)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), original)
        self.assertIn(b"$musk-five-step", (self.skill / "agents/openai.yaml").read_bytes())
        self.assertNotIn(b"$work-like-musk", (self.skill / "agents/openai.yaml").read_bytes())

    def test_rejects_foreign_or_malformed_entrypoint_before_changes(self):
        self.skill.mkdir()
        cases = [ORIGINAL.replace(b"work-like-musk", b"another-skill"),
                 ORIGINAL + b"<!-- five-step-hud:start -->\nbroken", ORIGINAL + LEGACY_SECTION * 2]
        for content in cases:
            with self.subTest(content=content):
                (self.skill / "SKILL.md").write_bytes(content)
                result = self.invoke()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual((self.skill / "SKILL.md").read_bytes(), content)
                self.assertFalse(self.backups.exists())

    def test_custom_guidance_and_crlf_survive_repeated_installation(self):
        self.skill.mkdir()
        original = ORIGINAL.replace(b"\n", b"\r\n")
        (self.skill / "SKILL.md").write_bytes(original + LEGACY_SECTION.replace(b"\n", b"\r\n"))
        for _ in range(2):
            result = self.invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.skill / "SKILL.md").read_bytes(), original)

    @unittest.skipIf(os.name == "nt", "POSIX symlinks and mode bits")
    def test_entrypoint_symlink_and_mode_survive(self):
        self.skill.mkdir()
        target = self.base / "source.md"
        target.write_bytes(ORIGINAL + LEGACY_SECTION)
        target.chmod(0o640)
        (self.skill / "SKILL.md").symlink_to(target)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.skill / "SKILL.md").is_symlink())
        self.assertEqual(target.read_bytes(), ORIGINAL)
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)

    @unittest.skipUnless(sys.platform == "darwin", "macOS extended attributes")
    def test_migration_preserves_extended_attributes_and_backups(self):
        self.legacy_install()
        target = self.skill / "SKILL.md"
        subprocess.run(["xattr", "-w", "com.example.work-like-musk", "keep metadata", str(target)], check=True)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(subprocess.check_output(["xattr", "-p", "com.example.work-like-musk", str(target)]).strip(), b"keep metadata")
        backup = Path(json.loads(result.stdout)["backupPath"]) / "SKILL.md"
        self.assertEqual(subprocess.check_output(["xattr", "-p", "com.example.work-like-musk", str(backup)]).strip(), b"keep metadata")

    @unittest.skipIf(os.name == "nt", "POSIX symlinks")
    def test_retiring_a_legacy_symlink_preserves_its_external_target(self):
        self.legacy_install()
        target = self.skill / "scripts/five_step.py"
        target.unlink()
        external = self.base / "external.py"
        external.write_bytes(b"shared original")
        target.symlink_to(external)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(target.is_symlink())
        self.assertEqual(external.read_bytes(), b"shared original")
        saved = Path(json.loads(result.stdout)["backupPath"]) / "scripts/five_step.py"
        self.assertTrue(saved.is_symlink())
        self.assertEqual(os.readlink(saved), str(external))

    @unittest.skipIf(os.name == "nt", "POSIX symlinks")
    def test_shared_legacy_directory_is_not_traversed(self):
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL + LEGACY_SECTION)
        external = self.base / "shared"
        external.mkdir()
        target = external / "five_step.py"
        target.write_bytes(b"shared original")
        (self.skill / "scripts").symlink_to(external, target_is_directory=True)
        result = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("linked", result.stderr)
        self.assertEqual(target.read_bytes(), b"shared original")
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL + LEGACY_SECTION)

    def test_failed_legacy_removal_restores_the_complete_previous_install(self):
        installer = self.legacy_install()
        before = self.snapshot()
        real_replace = os.replace
        failed = False
        def fail_removal(source, target):
            nonlocal failed
            if Path(source) == self.skill / "assets/FiveStepHUD.app" and not failed:
                failed = True
                raise OSError("Injected removal failure")
            return real_replace(source, target)
        with mock.patch.object(installer.os, "replace", side_effect=fail_removal):
            with self.assertRaisesRegex(OSError, "Injected removal"):
                installer.install(self.skill, self.backups)
        self.assertEqual(self.snapshot(), before)
        manifest, = self.backups.glob("*/manifest.json")
        self.assertEqual(json.loads(manifest.read_bytes())["status"], "rolled_back")
        self.assertEqual(self.invoke().returncode, 0)

    def test_unfinished_legacy_installation_blocks_cleanup_across_backup_roots(self):
        installer = self.legacy_install()
        before = self.snapshot()
        for root in (".codex/skill-backups/work-like-musk-hud", ".codex/skill-backups/musk-five-step-hud", ".work-like-musk/skill-backups"):
            with self.subTest(root=root):
                personal = self.base / root.split("/")[0].lstrip(".")
                manifest = personal / root / "unfinished/manifest.json"
                manifest.parent.mkdir(parents=True)
                original = json.dumps({"skillPath": str(self.skill), "status": "installing"})
                manifest.write_text(original, encoding="utf-8")
                with mock.patch.object(installer.Path, "home", return_value=personal):
                    with self.assertRaisesRegex(ValueError, "unfinished installation"):
                        installer.install(self.skill, self.backups)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(manifest.read_text(encoding="utf-8"), original)

    def test_completed_backups_can_be_moved_before_upgrade(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.backups.rename(self.base / "archived-backups")
        self.backups = self.base / "other-backups"
        upgraded = self.invoke()
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertEqual(Path(json.loads(upgraded.stdout)["backupPath"]).parent, self.backups)

    def test_competing_backup_roots_share_the_skill_lock(self):
        installer = self.installer_module()
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        alternative = self.base / "other-backups"
        script = ('import importlib.util, sys\nfrom pathlib import Path\n'
                  'spec = importlib.util.spec_from_file_location("installer", sys.argv[1])\n'
                  'installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)\n'
                  'try:\n'
                  ' installer.install(Path(sys.argv[2]), Path(sys.argv[3]))\n'
                  ' print("installed")\n'
                  'except BlockingIOError:\n print("busy")\n')
        real_copy = installer.copy_item
        competitors = []

        def compete_during_copy(source, target):
            if not competitors:
                competitors.append(subprocess.run([sys.executable, "-c", script, str(INSTALLER), str(self.skill), str(alternative)],
                                                  capture_output=True, text=True, timeout=20))
            return real_copy(source, target)

        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"), \
             mock.patch.object(installer, "copy_item", side_effect=compete_during_copy):
            installer.install(self.skill, self.backups)
        self.assertEqual(competitors[0].returncode, 0, competitors[0].stderr)
        self.assertEqual(competitors[0].stdout.strip(), "busy")
        self.assertFalse(alternative.exists())


    def test_forced_exit_during_staging_keeps_the_transaction_guard(self):
        installer = self.installer_module()
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        script = ('import importlib.util, os, sys\nfrom pathlib import Path\n'
                  'spec = importlib.util.spec_from_file_location("installer", sys.argv[1])\n'
                  'installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)\n'
                  'real_mkdtemp = installer.tempfile.mkdtemp\n'
                  'def exit_during_staging(*args, **kwargs):\n'
                  ' directory = real_mkdtemp(*args, **kwargs)\n'
                  ' if kwargs.get("prefix") == ".five-step-install-": os._exit(73)\n'
                  ' return directory\n'
                  'installer.tempfile.mkdtemp = exit_during_staging\n'
                  'installer.install(Path(sys.argv[2]), Path(sys.argv[3]))\n')
        result = subprocess.run([sys.executable, "-c", script, str(INSTALLER), str(self.skill), str(self.backups)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 73, result.stderr)
        manifest_path, = self.backups.glob("*/manifest.json")
        self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))["status"], "installing")
        before = set(self.skill.rglob("*"))
        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"):
            with self.assertRaisesRegex(ValueError, "unfinished installation"):
                installer.install(self.skill, self.base / "other-backups")
        self.assertEqual(set(self.skill.rglob("*")), before)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)


    def test_failed_completion_record_keeps_the_unfinished_manifest(self):
        installer = self.installer_module()
        real_replace = os.replace

        def fail_completion_record(source, target):
            if Path(target).name == "manifest.json" and json.loads(Path(source).read_bytes())["status"] == "installed":
                raise OSError("Injected completion record failure")
            return real_replace(source, target)

        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"), \
             mock.patch.object(installer.os, "replace", side_effect=fail_completion_record):
            with self.assertRaisesRegex(OSError, "completion record failure"):
                installer.install(self.skill, self.backups)
        manifest_path, = self.backups.glob("*/manifest.json")
        original = manifest_path.read_bytes()
        self.assertEqual(json.loads(original)["status"], "installing")
        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"):
            with self.assertRaisesRegex(ValueError, "unfinished installation"):
                installer.install(self.skill, self.base / "other-backups")
        self.assertEqual(manifest_path.read_bytes(), original)


    def test_manifest_write_retries_a_temporary_windows_sharing_violation(self):
        installer = self.installer_module()
        manifest = self.base / "manifest.json"
        manifest.write_text('{"status":"installing"}', encoding="utf-8")
        real_replace = os.replace
        attempts = []
        sharing_error = PermissionError(13, "Fixture sharing violation")
        sharing_error.winerror = 5

        def replace_after_two_readers(source, target):
            attempts.append(target)
            if len(attempts) <= 2:
                raise sharing_error
            return real_replace(source, target)

        with mock.patch.object(installer.sys, "platform", "win32"), \
             mock.patch.object(installer.os, "replace", side_effect=replace_after_two_readers):
            try:
                installer.write_json(manifest, {"status": "installed"})
            except OSError as error:
                self.fail(f"Temporary Windows reader prevented manifest completion: {error}")
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), {"status": "installed"})
        self.assertEqual(list(self.base.glob(".manifest.json-*")), [])


    def test_manifest_write_bounds_windows_sharing_retries(self):
        installer = self.installer_module()
        manifest = self.base / "manifest.json"
        original = b'{"status":"installing"}'
        manifest.write_bytes(original)
        sharing_error = PermissionError(13, "Fixture persistent sharing violation")
        sharing_error.winerror = 32
        with mock.patch.object(installer.sys, "platform", "win32"), \
             mock.patch.object(installer.os, "replace", side_effect=sharing_error) as replace:
            with self.assertRaisesRegex(OSError, "persistent sharing violation"):
                installer.write_json(manifest, {"status": "installed"})
        self.assertEqual(replace.call_count, 5)
        self.assertEqual(manifest.read_bytes(), original)
        self.assertEqual(list(self.base.glob(".manifest.json-*")), [])


    def test_manifest_write_does_not_retry_other_errors_or_platforms(self):
        installer = self.installer_module()
        manifest = self.base / "manifest.json"
        original = b'{"status":"installing"}'
        manifest.write_bytes(original)
        for host, code in [("win32", 87), ("win32", None), ("darwin", 5), ("linux", 32)]:
            with self.subTest(host=host, winerror=code):
                error = OSError(13, "Fixture replacement failure")
                if code is not None:
                    error.winerror = code
                with mock.patch.object(installer.sys, "platform", host), \
                     mock.patch.object(installer.os, "replace", side_effect=error) as replace:
                    with self.assertRaisesRegex(OSError, "replacement failure"):
                        installer.write_json(manifest, {"status": "installed"})
                self.assertEqual(replace.call_count, 1)
                self.assertEqual(manifest.read_bytes(), original)
                self.assertEqual(list(self.base.glob(".manifest.json-*")), [])


    @unittest.skipUnless(sys.platform == "win32", "Requires Windows reader/delete sharing semantics")
    def test_manifest_write_recovers_after_a_windows_reader_process_releases_it(self):
        installer = self.installer_module()
        manifest = self.base / "manifest.json"
        manifest.write_text('{"status":"installing"}', encoding="utf-8")
        script = ('import sys\n'
                  'with open(sys.argv[1], "r", encoding="utf-8") as manifest:\n'
                  ' print("ready", flush=True)\n'
                  ' sys.stdin.readline()\n')
        reader = subprocess.Popen([sys.executable, "-c", script, str(manifest)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        real_replace = os.replace
        sharing_errors = []

        def release_reader_after_real_sharing_violation(source, target):
            try:
                return real_replace(source, target)
            except OSError as error:
                if getattr(error, "winerror", None) in (5, 32):
                    sharing_errors.append(error.winerror)
                    reader.stdin.write("\n")
                    reader.stdin.flush()
                    reader.wait(timeout=10)
                raise

        try:
            self.assertEqual(reader.stdout.readline().strip(), "ready")
            with mock.patch.object(installer.os, "replace", side_effect=release_reader_after_real_sharing_violation):
                installer.write_json(manifest, {"status": "installed"})
            self.assertEqual(len(sharing_errors), 1)
            self.assertIn(sharing_errors[0], (5, 32))
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), {"status": "installed"})
        finally:
            if reader.poll() is None:
                reader.kill()
            reader.communicate(timeout=10)


    def test_foreign_directory_and_unfinished_transaction_are_preserved(self):
        self.skill.mkdir()
        owned = self.skill / "unrelated.txt"
        owned.write_text("another task", encoding="utf-8")
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(self.skill.iterdir()), [owned])
        self.skill = self.base / "fresh"
        manifest = self.backups / "unfinished/manifest.json"
        manifest.parent.mkdir(parents=True)
        original = json.dumps({"skillPath": str(self.skill), "status": "installing"})
        manifest.write_text(original, encoding="utf-8")
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("unfinished installation", result.stderr)
        self.assertFalse(self.skill.exists())
        self.assertEqual(manifest.read_text(encoding="utf-8"), original)


    def test_fresh_install_rollback_leaves_no_skill_directory(self):
        installer = self.installer_module()
        real_replace = os.replace

        def fail_entrypoint(source, target):
            if Path(target) == self.skill / "SKILL.md":
                raise OSError("Injected entrypoint failure")
            return real_replace(source, target)

        with mock.patch.object(installer.os, "replace", side_effect=fail_entrypoint):
            with self.assertRaisesRegex(OSError, "Injected"):
                installer.install(self.skill, self.backups)
        self.assertFalse(self.skill.exists())



if __name__ == "__main__":
    unittest.main()
