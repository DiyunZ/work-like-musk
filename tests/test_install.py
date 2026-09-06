import json
import importlib.util
import io
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
ORIGINAL = b"---\nname: work-like-musk\ndescription: Apply five ordered steps.\n---\n\n# Existing guidance\n\nKeep this paragraph exactly.\n"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.skill = self.base / "skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        (self.skill / "SKILL.md").chmod(0o640)
        (self.skill / "agents").mkdir()
        (self.skill / "agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        self.app = self.base / "FiveStepHUD.app"
        executable = self.app / "Contents/MacOS/FiveStepHUD"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture executable")
        executable.chmod(0o755)
        (self.app / "Contents/Info.plist").write_text("fixture metadata")

    def invoke(self, language="en"):
        command = [sys.executable, str(INSTALLER), "--skill", str(self.skill), "--app", str(self.app),
                   "--backup-root", str(self.base / "backups")]
        if language is not None:
            command += ["--language", language]
        return subprocess.run(command, capture_output=True, text=True)

    def install(self, language="en"):
        result = self.invoke(language)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def installer_module(self):
        spec = importlib.util.spec_from_file_location("hud_installer", INSTALLER)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        return installer

    def test_language_selection_updates_guide_and_preserves_original_instructions(self):
        for language, expected in [("zh-CN", "简体中文"), ("en", "English")]:
            result = self.install(language)
            self.assertEqual(result["language"], language)
            self.assertEqual(json.loads((self.skill / "assets/hud-config.json").read_text()), {"language": language})
            installed = (self.skill / "SKILL.md").read_text()
            self.assertTrue(installed.startswith(ORIGINAL.decode()))
            self.assertIn(expected, installed)
            self.assertEqual(installed.count("<!-- five-step-hud:start -->"), 1)
            guide = "live-progress.zh-CN.md" if language == "zh-CN" else "live-progress.md"
            self.assertEqual((self.skill / "references/live-progress.md").read_bytes(),
                             (ROOT / "skills/work-like-musk/references" / guide).read_bytes())

    def test_reinstall_without_language_preserves_previous_choice(self):
        self.install("zh-CN")
        result = self.install(None)
        self.assertEqual(result["language"], "zh-CN")
        self.assertIn("简体中文", (self.skill / "SKILL.md").read_text())

    def test_noninteractive_first_install_requires_a_language_without_mutation(self):
        result = self.invoke(None)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--language", result.stderr)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertFalse((self.base / "backups").exists())

    def test_invalid_language_is_rejected_without_mutation(self):
        result = self.invoke("fr")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertFalse((self.skill / "assets").exists())

    def test_invalid_saved_language_is_preserved_until_explicitly_replaced(self):
        self.install()
        config = self.skill / "assets/hud-config.json"
        for invalid in ['{"language":"fr"}', '{broken']:
            config.write_text(invalid)
            self.assertEqual(self.invoke(None).returncode, 2)
            self.assertEqual(config.read_text(), invalid)
        self.install("zh-CN")
        self.assertEqual(json.loads(config.read_text()), {"language": "zh-CN"})

    def test_interactive_choice_reprompts_and_preserves_saved_default(self):
        installer = self.installer_module()
        with mock.patch.object(installer.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", side_effect=["wrong", "1"]), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            self.assertEqual(installer.choose_language(self.skill, None), "zh-CN")
        self.install("zh-CN")
        with mock.patch.object(installer.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", return_value=""), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            self.assertEqual(installer.choose_language(self.skill, None), "zh-CN")

    def test_cancelled_interactive_choice_does_not_install(self):
        installer = self.installer_module()
        with mock.patch.object(installer.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", side_effect=EOFError), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            with self.assertRaisesRegex(ValueError, "cancelled"):
                installer.choose_language(self.skill, None)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertFalse((self.skill / "assets").exists())

    def test_install_twice_preserves_entrypoint_metadata_and_backups(self):
        metadata = (self.skill / "agents/openai.yaml").read_bytes()
        first = self.install()
        installed = (self.skill / "SKILL.md").read_bytes()
        self.assertTrue(installed.startswith(ORIGINAL))
        self.assertEqual((self.skill / "SKILL.md").stat().st_mode & 0o777, 0o640)
        self.assertEqual((Path(first["backupPath"]) / "SKILL.md").read_bytes(), ORIGINAL)
        second = self.install()
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), installed)
        self.assertEqual(installed.count(b"<!-- five-step-hud:start -->"), 1)
        self.assertEqual((self.skill / "agents/openai.yaml").read_bytes(), metadata)
        self.assertEqual((self.skill / "scripts/five_step.py").read_bytes(), (ROOT / "skills/work-like-musk/scripts/five_step.py").read_bytes())
        self.assertEqual((self.skill / "references/live-progress.md").read_bytes(), (ROOT / "skills/work-like-musk/references/live-progress.md").read_bytes())
        self.assertEqual((Path(second["backupPath"]) / "scripts/five_step.py").read_bytes(), (ROOT / "skills/work-like-musk/scripts/five_step.py").read_bytes())
        self.assertTrue(os.access(self.skill / "assets/FiveStepHUD.app/Contents/MacOS/FiveStepHUD", os.X_OK))

    def test_install_twice_preserves_crlf_entrypoint_prefix(self):
        original = ORIGINAL.replace(b"\n", b"\r\n")
        (self.skill / "SKILL.md").write_bytes(original)

        self.install()
        installed = (self.skill / "SKILL.md").read_bytes()
        self.assertTrue(installed.startswith(original))
        self.assertEqual(installed.count(b"<!-- five-step-hud:start -->"), 1)

        self.install()
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), installed)
        self.assertEqual(installed.count(b"<!-- five-step-hud:end -->"), 1)

    def test_entrypoint_symlink_and_target_mode_preserved(self):
        target = self.base / "source-entrypoint.md"
        (self.skill / "SKILL.md").rename(target)
        (self.skill / "SKILL.md").symlink_to(target)
        self.install()
        self.assertTrue((self.skill / "SKILL.md").is_symlink())
        self.assertTrue(target.read_bytes().startswith(ORIGINAL))
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)

    def test_rejects_unrelated_or_broken_managed_section_without_mutation(self):
        for content in [ORIGINAL.replace(b"work-like-musk", b"another-skill"),
                        ORIGINAL + b"\n<!-- five-step-hud:start -->\nbroken"]:
            (self.skill / "SKILL.md").write_bytes(content)
            result = self.invoke()
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual((self.skill / "SKILL.md").read_bytes(), content)
            self.assertFalse((self.skill / "scripts").exists())

    def test_missing_app_does_not_change_skill(self):
        (self.app / "Contents/MacOS/FiveStepHUD").unlink()
        self.assertEqual(self.invoke().returncode, 2)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)

    def test_failure_rolls_back_previously_replaced_files(self):
        self.install()
        (self.skill / "scripts/five_step.py").write_text("original CLI content")
        before = (self.skill / "SKILL.md").read_bytes()
        installer = self.installer_module()
        real_replace = os.replace

        def fail_guide(source, target):
            if Path(target) == (self.skill / "references/live-progress.md").resolve():
                raise OSError("Injected installation failure")
            return real_replace(source, target)

        with mock.patch.object(installer.os, "replace", side_effect=fail_guide):
            with self.assertRaisesRegex(OSError, "Injected"):
                installer.install(self.skill, self.app, self.base / "backups", language="zh-CN")
        self.assertEqual((self.skill / "scripts/five_step.py").read_text(), "original CLI content")
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), before)
        self.assertEqual(json.loads((self.skill / "assets/hud-config.json").read_text()), {"language": "en"})
        statuses = [json.loads(p.read_text())["status"] for p in (self.base / "backups").glob("*/manifest.json")]
        self.assertIn("rolled_back", statuses)

    def test_support_symlink_and_extended_attributes_survive(self):
        self.install()
        target = self.base / "source-cli.py"
        (self.skill / "scripts/five_step.py").rename(target)
        (self.skill / "scripts/five_step.py").symlink_to(target)
        subprocess.run(["/usr/bin/xattr", "-w", "org.fivestephud.test", "keep-me", str(self.skill / "SKILL.md")], check=True)
        self.install()
        self.assertTrue((self.skill / "scripts/five_step.py").is_symlink())
        self.assertEqual(target.read_bytes(), (ROOT / "skills/work-like-musk/scripts/five_step.py").read_bytes())
        result = subprocess.run(["/usr/bin/xattr", "-p", "org.fivestephud.test", str(self.skill / "SKILL.md")],
                                check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "keep-me")

    def test_fresh_install_contains_skill_and_hud(self):
        self.skill = self.base / "fresh-skill"
        result = self.install()
        source = ROOT / "skills/work-like-musk"
        for relative in ("agents/openai.yaml", "scripts/five_step.py",
                         "references/live-progress.md", "references/live-progress.zh-CN.md"):
            self.assertEqual((self.skill / relative).read_bytes(), (source / relative).read_bytes())
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), (source / "SKILL.md").read_bytes())
        self.assertTrue(os.access(self.skill / "assets/FiveStepHUD.app/Contents/MacOS/FiveStepHUD", os.X_OK))
        manifest = json.loads((Path(result["backupPath"]) / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "installed")

    def test_fresh_install_failure_leaves_no_partial_skill(self):
        self.skill = self.base / "fresh-skill"
        installer = self.installer_module()
        real_replace = os.replace

        def fail_entrypoint(source, target):
            if Path(target) == (self.skill / "SKILL.md").resolve():
                raise OSError("Injected entrypoint publication failure")
            return real_replace(source, target)

        with mock.patch.object(installer.os, "replace", side_effect=fail_entrypoint):
            with self.assertRaisesRegex(OSError, "Injected"):
                installer.install(self.skill, self.app, self.base / "backups", language="en")
        self.assertFalse(self.skill.exists())
        manifests = list((self.base / "backups").glob("*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text())["status"], "rolled_back")

    def test_existing_unrelated_directory_is_not_used(self):
        self.skill = self.base / "unrelated"
        self.skill.mkdir()
        (self.skill / "keep.txt").write_text("unrelated work")
        result = self.invoke()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(list(self.skill.iterdir()), [self.skill / "keep.txt"])
        self.assertEqual((self.skill / "keep.txt").read_text(), "unrelated work")

    def test_fresh_install_refuses_unfinished_transaction(self):
        self.skill = self.base / "fresh-skill"
        manifest = self.base / "backups/previous/manifest.json"
        manifest.parent.mkdir(parents=True)
        previous = json.dumps({"skillPath": str(self.skill.resolve()), "status": "installing"})
        manifest.write_text(previous)
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("unfinished installation", result.stderr)
        self.assertFalse(self.skill.exists())
        self.assertEqual(manifest.read_text(), previous)

    def fixture_checkout(self, fail_build=False):
        checkout = self.base / "checkout"
        (checkout / "scripts").mkdir(parents=True)
        shutil.copytree(ROOT / "skills/work-like-musk", checkout / "skills/work-like-musk")
        (checkout / "scripts/build.py").write_text(
            "from pathlib import Path\nimport shutil\n"
            "root = Path(__file__).resolve().parents[1]\n"
            "(root / 'build-attempted').write_text('yes')\n" +
            ("raise SystemExit(3)\n" if fail_build else
             f"shutil.copytree({str(self.app)!r}, root / 'dist/FiveStepHUD.app')\n"))
        return checkout

    def run_main(self, installer, checkout, extra=()):
        args = [str(INSTALLER), "--skill", str(self.skill), "--language", "en",
                "--backup-root", str(self.base / "backups"), *extra]
        with mock.patch.object(installer, "ROOT", checkout), \
             mock.patch.object(installer.sys, "argv", args), \
             mock.patch.object(installer.sys, "stdout", new_callable=io.StringIO), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            return installer.main()

    def test_main_builds_hud_and_installs_complete_product(self):
        self.skill = self.base / "fresh-skill"
        installer = self.installer_module()
        checkout = self.fixture_checkout()
        self.assertEqual(self.run_main(installer, checkout), 0)
        self.assertTrue((checkout / "build-attempted").exists())
        self.assertTrue((self.skill / "SKILL.md").exists())
        self.assertTrue((self.skill / "assets/FiveStepHUD.app/Contents/MacOS/FiveStepHUD").exists())

    def test_failed_build_preserves_existing_installation(self):
        installer = self.installer_module()
        checkout = self.fixture_checkout(fail_build=True)
        self.assertEqual(self.run_main(installer, checkout), 2)
        self.assertTrue((checkout / "build-attempted").exists())
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertFalse((self.skill / "assets").exists())
        self.assertFalse((self.base / "backups").exists())

    def test_unsupported_host_does_not_install_partial_product(self):
        installer = self.installer_module()
        with mock.patch.object(installer.sys, "platform", "linux"):
            self.assertEqual(self.run_main(installer, ROOT, ("--app", str(self.app))), 2)
        self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
        self.assertFalse((self.skill / "assets").exists())


if __name__ == "__main__":
    unittest.main()
