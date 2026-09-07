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
LEGACY_DESCRIPTION = ('description: "Use for project coaching with an integrated live progress HUD in local Codex on macOS 14+, '
                      'or when continuing a project already using Work Like Musk. Keep factual questions and straightforward '
                      'edits scoped to their immediate purpose."')


@unittest.skipUnless(sys.platform == "darwin", "Native app and macOS metadata regression suite")
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        home = mock.patch.dict(os.environ, {"HOME": str(self.base / "home"), "USERPROFILE": str(self.base / "home")})
        home.start()
        self.addCleanup(home.stop)
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

    def test_native_install_does_not_provision_qt(self):
        installer = self.installer_module()
        with mock.patch.object(installer, "ensure_portable_runtime", side_effect=AssertionError("Native install requested Qt")):
            installer.install(self.skill, self.app, self.base / "backups", backend="native")
        self.assertFalse((self.skill / "assets/portable-runtime.json").exists())
        self.assertFalse((self.base / "home/.work-like-musk/runtimes").exists())

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


class PortableInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        home = mock.patch.dict(os.environ, {"HOME": str(self.base / "home"), "USERPROFILE": str(self.base / "home")})
        home.start()
        self.addCleanup(home.stop)
        self.skill = self.base / "skill"
        self.backups = self.base / "backups"

    def invoke(self, *extra, language="en"):
        args = [sys.executable, str(INSTALLER), "--skill", str(self.skill),
                "--backup-root", str(self.backups), "--agent", "claude-code", "--hud", "portable"]
        if language is not None:
            args += ["--language", language]
        return subprocess.run([*args, *extra], capture_output=True, text=True, encoding="utf-8")

    def installer_module(self):
        spec = importlib.util.spec_from_file_location("portable_installer", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_fresh_portable_install_is_complete_without_a_native_app(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = json.loads(result.stdout)
        self.assertEqual(installed["backend"], "portable")
        self.assertFalse((self.skill / "assets/FiveStepHUD.app").exists())
        for relative in ("SKILL.md", "agents/openai.yaml", "scripts/five_step.py",
                         "scripts/runtime_support.py", "scripts/portable_hud.py", "references/live-progress.md"):
            self.assertTrue((self.skill / relative).is_file(), relative)
        runtime = json.loads((self.skill / "assets/runtime-config.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime, {"schemaVersion": 1, "agent": "claude-code", "backend": "portable"})
        portable = self.skill / "assets/portable-runtime.json"
        self.assertTrue(portable.is_file())
        self.assertEqual(json.loads(portable.read_text(encoding="utf-8")),
                         {"schemaVersion": 1, "pythonExecutable": str(Path(sys.executable).absolute())})
        manifest = json.loads((Path(installed["backupPath"]) / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "installed")
        run = subprocess.run([sys.executable, str(self.skill / "scripts/five_step.py"), "setup",
                              "--project", str(self.base), "--new-task", "--no-open"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["taskId"].startswith("wlm-"))

    def test_each_agent_installs_to_its_documented_personal_directory(self):
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
                 mock.patch.object(installer.sys, "argv", [str(INSTALLER), "--agent", agent, "--hud", "portable",
                                   "--language", "en", "--backup-root", str(self.backups)]), \
                 mock.patch.object(installer.sys, "stdout", new_callable=io.StringIO), \
                 mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
                self.assertEqual(installer.main(), 0, installer.sys.stderr.getvalue())
            self.assertTrue((destination / "SKILL.md").is_file(), str(destination))
            config = json.loads((destination / "assets/runtime-config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["agent"], agent)

    def test_upgrade_preserves_custom_guidance_metadata_and_language(self):
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        metadata = self.skill / "agents/openai.yaml"
        metadata.parent.mkdir()
        custom = b"policy:\n  allow_implicit_invocation: false\n"
        metadata.write_bytes(custom)
        result = self.invoke(language="zh-CN")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.skill / "SKILL.md").read_bytes().startswith(ORIGINAL))
        self.assertEqual(metadata.read_bytes(), custom)
        self.assertEqual((self.skill / "references/live-progress.md").read_bytes(),
                         (ROOT / "skills/work-like-musk/references/live-progress.zh-CN.md").read_bytes())
        upgraded = self.invoke(language=None)
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertEqual(json.loads(upgraded.stdout)["language"], "zh-CN")

    def qt_subprocess_fixture(self, pip_error=None, invalid_qt=False):
        state = {"commands": [], "ready": False, "pip_error": pip_error, "invalid_qt": invalid_qt}
        real_run = subprocess.run

        def run(command, **kwargs):
            if len(command) >= 3 and command[1] == "-c" and "PySide6" in command[2]:
                state["commands"].append(command)
                ready = command[0] != str(Path(sys.executable).absolute()) and state["ready"] and not state["invalid_qt"]
                return subprocess.CompletedProcess(command, 0 if ready else 1, "", "" if ready else "Qt import or version is invalid")
            if command[1:3] == ["-m", "venv"]:
                state["commands"].append(command)
                environment = Path(command[3])
                python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                python.parent.mkdir(parents=True, exist_ok=True)
                python.write_bytes(b"fixture private interpreter")
                (environment / "pyvenv.cfg").write_text("fixture venv", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[1:3] == ["-m", "pip"]:
                state["commands"].append(command)
                state["ready"] = not state["pip_error"]
                return subprocess.CompletedProcess(command, 1 if state["pip_error"] else 0, "", state["pip_error"] or "")
            return real_run(command, **kwargs)

        return state, run

    def test_missing_qt_is_provisioned_privately_and_reused_at_its_final_path(self):
        installer = self.installer_module()
        state, run = self.qt_subprocess_fixture()
        with mock.patch.object(installer.subprocess, "run", side_effect=run), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            installer.install(self.skill, None, self.backups, backend="portable")
            portable = self.skill / "assets/portable-runtime.json"
            self.assertTrue(portable.is_file())
            config = json.loads(portable.read_text(encoding="utf-8"))
            environment = self.base / "home/.work-like-musk/runtimes" / f"pyside6-py{sys.version_info.major}.{sys.version_info.minor}"
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            self.assertEqual(config, {"schemaVersion": 1, "pythonExecutable": str(python)})
            installer.install(self.base / "second-skill", None, self.backups, agent="cursor", backend="portable")
        creations = [command for command in state["commands"] if command[1:3] == ["-m", "venv"]]
        installs = [command for command in state["commands"] if command[1:3] == ["-m", "pip"]]
        self.assertEqual(creations, [[str(Path(sys.executable).absolute()), "-m", "venv", str(environment)]])
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0][0], str(python))
        self.assertIn("PySide6-Essentials>=6.8,<7", installs[0])
        self.assertIn("https://pypi.org/simple", installs[0])

    def test_failed_qt_setup_preserves_the_skill_and_reports_the_dependency_error(self):
        installer = self.installer_module()
        for failure in ("network", "invalid_qt"):
            with self.subTest(failure=failure):
                self.skill = self.base / failure / "skill"
                self.skill.mkdir(parents=True)
                (self.skill / "SKILL.md").write_bytes(ORIGINAL)
                portable = self.skill / "assets/portable-runtime.json"
                portable.parent.mkdir()
                original_config = b'{"schemaVersion":1,"pythonExecutable":"preserve existing configuration"}'
                portable.write_bytes(original_config)
                personal = self.base / failure / "home"
                state, run = self.qt_subprocess_fixture(pip_error="Network unavailable" if failure == "network" else None,
                                                        invalid_qt=failure == "invalid_qt")
                args = [str(INSTALLER), "--skill", str(self.skill), "--backup-root", str(self.backups),
                        "--agent", "cursor", "--hud", "portable", "--language", "en"]
                with mock.patch.object(installer.Path, "home", return_value=personal), \
                     mock.patch.object(installer.subprocess, "run", side_effect=run), \
                     mock.patch.object(installer.sys, "argv", args), \
                     mock.patch.object(installer.sys, "stdout", new_callable=io.StringIO), \
                     mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO) as error:
                    self.assertEqual(installer.main(), 2)
                self.assertIn("Qt runtime setup failed", error.getvalue())
                self.assertIn("Network unavailable" if failure == "network" else "Qt import or version is invalid", error.getvalue())
                self.assertEqual((self.skill / "SKILL.md").read_bytes(), ORIGINAL)
                self.assertEqual(portable.read_bytes(), original_config)
                self.assertFalse(self.backups.exists())
                record, = (personal / ".work-like-musk/runtimes").glob("*.json")
                self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["status"], "failed")

    def test_qt_probe_requires_a_supported_version_and_loadable_widgets(self):
        installer = self.installer_module()
        package_root = self.base / "probe-packages"
        package = package_root / "PySide6"
        package.mkdir(parents=True)
        widgets = package / "QtWidgets.py"
        widgets.write_text("class QApplication: pass\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PYTHONPATH": str(package_root), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONOPTIMIZE": "1"}):
            for version, supported in [("6.7.3", False), ("6.8.0", True), ("6.11.2", True), ("7.0.0", False), ("broken", False)]:
                with self.subTest(version=version):
                    (package / "__init__.py").write_text(f"__version__ = {version!r}\n", encoding="utf-8")
                    error = installer.portable_runtime_error(Path(sys.executable).absolute())
                    self.assertEqual(error is None, supported, error)
            (package / "__init__.py").write_text("__version__ = '6.11.2'\n", encoding="utf-8")
            widgets.write_text("raise ImportError('Qt library cannot load')\n", encoding="utf-8")
            self.assertIn("Qt library cannot load", installer.portable_runtime_error(Path(sys.executable).absolute()))

    def test_failed_qt_download_can_retry_in_the_same_owned_environment(self):
        installer = self.installer_module()
        state, run = self.qt_subprocess_fixture(pip_error="Network unavailable")
        with mock.patch.object(installer.subprocess, "run", side_effect=run), \
             mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO):
            with self.assertRaisesRegex(ValueError, "Network unavailable"):
                installer.install(self.skill, None, self.backups, backend="portable")
            record, = (self.base / "home/.work-like-musk/runtimes").glob("*.json")
            python = Path(json.loads(record.read_text(encoding="utf-8"))["pythonExecutable"])
            kept = python.parent.parent / "keep.txt"
            kept.write_bytes(b"preserve owned runtime data")
            state["pip_error"] = None
            installer.install(self.skill, None, self.backups, backend="portable")
        self.assertEqual(kept.read_bytes(), b"preserve owned runtime data")
        self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["status"], "ready")
        self.assertEqual(len([command for command in state["commands"] if command[1:3] == ["-m", "venv"]]), 1)
        self.assertEqual(json.loads((self.skill / "assets/portable-runtime.json").read_text(encoding="utf-8")),
                         {"schemaVersion": 1, "pythonExecutable": str(python)})

    def test_portable_configuration_changed_during_setup_is_preserved(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        installer = self.installer_module()
        config = self.skill / "assets/portable-runtime.json"
        changed = b'{"schemaVersion":1,"pythonExecutable":"another writer owns this edit"}'
        before_backups = set(self.backups.glob("*/manifest.json"))

        def change_during_setup():
            config.write_bytes(changed)
            return Path(sys.executable).absolute()

        with mock.patch.object(installer, "ensure_portable_runtime", side_effect=change_during_setup):
            with self.assertRaisesRegex(ValueError, "Portable runtime configuration changed during preflight"):
                installer.install(self.skill, None, self.backups, backend="portable")
        self.assertEqual(config.read_bytes(), changed)
        self.assertEqual(set(self.backups.glob("*/manifest.json")), before_backups)

    def test_foreign_or_unfinished_skill_does_not_start_qt_provisioning(self):
        installer = self.installer_module()
        for unfinished in (False, True):
            with self.subTest(unfinished=unfinished):
                self.skill = self.base / str(unfinished) / "skill"
                self.skill.mkdir(parents=True)
                (self.skill / ("SKILL.md" if unfinished else "keep.txt")).write_bytes(ORIGINAL)
                if unfinished:
                    manifest = self.backups / "unfinished/manifest.json"
                    manifest.parent.mkdir(parents=True)
                    manifest.write_text(json.dumps({"skillPath": str(self.skill), "status": "installing"}), encoding="utf-8")
                state, run = self.qt_subprocess_fixture()
                with mock.patch.object(installer.subprocess, "run", side_effect=run):
                    with self.assertRaises(ValueError):
                        installer.install(self.skill, None, self.backups, backend="portable")
                self.assertFalse((self.base / "home/.work-like-musk/runtimes").exists())
                self.assertEqual(state["commands"], [])

    def test_concurrent_private_runtime_setup_does_not_modify_the_skill(self):
        installer = self.installer_module()
        runtimes = self.base / "home/.work-like-musk/runtimes"
        runtimes.mkdir(parents=True)
        name = f"pyside6-py{sys.version_info.major}.{sys.version_info.minor}"
        state, run = self.qt_subprocess_fixture()
        with (runtimes / (name + ".lock")).open("a+b") as lock, installer.file_lock(lock), \
             mock.patch.object(installer.subprocess, "run", side_effect=run):
            with self.assertRaisesRegex(ValueError, "Qt runtime setup is already running"):
                installer.install(self.skill, None, self.backups, backend="portable")
        self.assertFalse(self.skill.exists())
        self.assertFalse((runtimes / name).exists())
        self.assertFalse(self.backups.exists())

    def test_foreign_or_unfinished_private_runtime_is_preserved(self):
        installer = self.installer_module()
        for unfinished in (False, True):
            with self.subTest(unfinished=unfinished):
                personal = self.base / str(unfinished) / "home"
                runtimes = personal / ".work-like-musk/runtimes"
                name = f"pyside6-py{sys.version_info.major}.{sys.version_info.minor}"
                environment = runtimes / name
                environment.mkdir(parents=True)
                owned = environment / "keep.txt"
                owned.write_bytes(b"another task's work")
                if unfinished:
                    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                    (runtimes / (name + ".json")).write_text(json.dumps({"schemaVersion": 1,
                        "pythonExecutable": str(python), "status": "provisioning"}), encoding="utf-8")
                state, run = self.qt_subprocess_fixture()
                with mock.patch.object(installer.Path, "home", return_value=personal), \
                     mock.patch.object(installer.subprocess, "run", side_effect=run):
                    with self.assertRaisesRegex(ValueError, "Qt runtime.*inspection"):
                        installer.install(self.skill, None, self.backups, backend="portable")
                self.assertEqual(list(environment.iterdir()), [owned])
                self.assertFalse(self.skill.exists())

    def test_upgrade_migrates_only_the_legacy_stock_description(self):
        self.skill.mkdir()
        original = ORIGINAL.decode().replace("description: Apply five ordered steps.", LEGACY_DESCRIPTION)
        (self.skill / "SKILL.md").write_bytes(original.replace("\n", "\r\n").encode())
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = (self.skill / "SKILL.md").read_bytes()
        self.assertIn(b"in local AI agents on Windows, Linux, or macOS", installed)
        self.assertNotIn(b"in local Codex on macOS 14+", installed)
        self.assertIn(b"# Existing guidance\r\n\r\nKeep this paragraph exactly.\r\n", installed)

    def test_upgrade_preserves_a_custom_description(self):
        self.skill.mkdir()
        original = ORIGINAL.replace(b"Apply five ordered steps.", b"My custom routing for local Codex on macOS 14+.")
        (self.skill / "SKILL.md").write_bytes(original)
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.skill / "SKILL.md").read_bytes().startswith(original))

    def test_alternate_backup_root_refuses_an_interrupted_installation(self):
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        installer = self.installer_module()
        real_replace = os.replace

        def interrupt_entrypoint(source, target):
            if Path(target) == self.skill / "SKILL.md":
                raise KeyboardInterrupt("Interrupted before entrypoint publication")
            return real_replace(source, target)

        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"), \
             mock.patch.object(installer.os, "replace", side_effect=interrupt_entrypoint):
            with self.assertRaises(KeyboardInterrupt):
                installer.install(self.skill, None, self.backups, agent="codex", backend="portable")
        manifest_path, = self.backups.glob("*/manifest.json")
        original_manifest = manifest_path.read_bytes()
        self.assertEqual(json.loads(original_manifest)["status"], "installing")
        before = {path.relative_to(self.skill): path.read_bytes() for path in self.skill.rglob("*") if path.is_file()}
        alternative = self.base / "other-backups"
        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"):
            with self.assertRaisesRegex(ValueError, "unfinished installation"):
                installer.install(self.skill, None, alternative, language="zh-CN", agent="cursor", backend="portable")
        self.assertEqual(manifest_path.read_bytes(), original_manifest)
        self.assertFalse(alternative.exists())
        self.assertEqual({path.relative_to(self.skill): path.read_bytes() for path in self.skill.rglob("*") if path.is_file()}, before)

    def test_completed_backups_can_be_removed_or_moved_before_an_upgrade(self):
        for action in ("remove", "move"):
            with self.subTest(action=action):
                self.skill = self.base / action / "skill"
                self.backups = self.base / action / "backups"
                first = self.invoke()
                self.assertEqual(first.returncode, 0, first.stderr)
                if action == "remove":
                    shutil.rmtree(self.backups)
                else:
                    self.backups.rename(self.backups.with_name("archived-backups"))
                self.backups = self.backups.with_name("other-backups")
                upgraded = self.invoke(language="zh-CN")
                self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
                result = json.loads(upgraded.stdout)
                self.assertEqual(Path(result["backupPath"]).parent, self.backups)
                self.assertEqual(result["language"], "zh-CN")

    def test_agent_switch_checks_both_legacy_default_backup_roots(self):
        installer = self.installer_module()
        for agent, old_root in [("cursor", ".codex/skill-backups/work-like-musk-hud"),
                                ("codex", ".work-like-musk/skill-backups")]:
            with self.subTest(agent=agent):
                personal = self.base / agent
                skill = personal / "shared-skill"
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_bytes(ORIGINAL)
                manifest = personal / old_root / "unfinished/manifest.json"
                manifest.parent.mkdir(parents=True)
                original = json.dumps({"skillPath": str(skill), "status": "installing"})
                manifest.write_text(original, encoding="utf-8")
                args = [str(INSTALLER), "--skill", str(skill), "--agent", agent, "--hud", "portable", "--language", "en"]
                with mock.patch.object(installer.Path, "home", return_value=personal), \
                     mock.patch.object(installer.sys, "argv", args), \
                     mock.patch.object(installer.sys, "stdout", new_callable=io.StringIO), \
                     mock.patch.object(installer.sys, "stderr", new_callable=io.StringIO) as error:
                    self.assertEqual(installer.main(), 2)
                self.assertIn("unfinished installation", error.getvalue())
                self.assertEqual((skill / "SKILL.md").read_bytes(), ORIGINAL)
                self.assertEqual(manifest.read_text(encoding="utf-8"), original)
                self.assertFalse((skill / "assets").exists())

    def test_competing_backup_roots_share_the_skill_lock(self):
        installer = self.installer_module()
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_bytes(ORIGINAL)
        alternative = self.base / "other-backups"
        script = ('import importlib.util, sys\nfrom pathlib import Path\n'
                  'spec = importlib.util.spec_from_file_location("installer", sys.argv[1])\n'
                  'installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)\n'
                  'try:\n'
                  ' installer.install(Path(sys.argv[2]), None, Path(sys.argv[3]), agent="cursor", backend="portable")\n'
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
            installer.install(self.skill, None, self.backups, agent="codex", backend="portable")
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
                  'installer.install(Path(sys.argv[2]), None, Path(sys.argv[3]), backend="portable")\n')
        result = subprocess.run([sys.executable, "-c", script, str(INSTALLER), str(self.skill), str(self.backups)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 73, result.stderr)
        manifest_path, = self.backups.glob("*/manifest.json")
        self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))["status"], "installing")
        before = set(self.skill.rglob("*"))
        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"):
            with self.assertRaisesRegex(ValueError, "unfinished installation"):
                installer.install(self.skill, None, self.base / "other-backups", backend="portable")
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
                installer.install(self.skill, None, self.backups, backend="portable")
        manifest_path, = self.backups.glob("*/manifest.json")
        original = manifest_path.read_bytes()
        self.assertEqual(json.loads(original)["status"], "installing")
        with mock.patch.object(installer.Path, "home", return_value=self.base / "home"):
            with self.assertRaisesRegex(ValueError, "unfinished installation"):
                installer.install(self.skill, None, self.base / "other-backups", backend="portable")
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

    def test_portable_install_rolls_back_files_and_configuration_on_failure(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = {path.relative_to(self.skill): path.read_bytes() for path in self.skill.rglob("*") if path.is_file()}
        installer = self.installer_module()
        other_python = self.base / "other-python"
        other_python.write_bytes(b"fixture alternate GUI interpreter")
        real_replace = os.replace

        def fail_guide(source, target):
            if Path(target) == self.skill / "references/live-progress.md":
                raise OSError("Injected portable installation failure")
            return real_replace(source, target)

        with mock.patch.object(installer.os, "replace", side_effect=fail_guide), \
             mock.patch.object(installer, "ensure_portable_runtime", return_value=other_python):
            with self.assertRaisesRegex(OSError, "Injected"):
                installer.install(self.skill, None, self.backups, language="zh-CN", agent="cursor", backend="portable")
        after = {path.relative_to(self.skill): path.read_bytes() for path in self.skill.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        statuses = [json.loads(path.read_text(encoding="utf-8"))["status"] for path in self.backups.glob("*/manifest.json")]
        self.assertIn("rolled_back", statuses)
        shutil.rmtree(self.backups)
        alternative = self.base / "other-backups"
        upgraded = self.invoke("--backup-root", str(alternative), "--agent", "cursor", language="zh-CN")
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        result = json.loads(upgraded.stdout)
        self.assertEqual(Path(result["backupPath"]).parent, alternative)
        self.assertEqual(json.loads((self.skill / "assets/runtime-config.json").read_text(encoding="utf-8"))["agent"], "cursor")

    def test_fresh_portable_install_rollback_leaves_no_skill_directory(self):
        installer = self.installer_module()
        real_replace = os.replace

        def fail_entrypoint(source, target):
            if Path(target) == self.skill / "SKILL.md":
                raise OSError("Injected entrypoint failure")
            return real_replace(source, target)

        with mock.patch.object(installer.os, "replace", side_effect=fail_entrypoint):
            with self.assertRaisesRegex(OSError, "Injected"):
                installer.install(self.skill, None, self.backups, language="en", agent="generic", backend="portable")
        self.assertFalse(self.skill.exists())


if __name__ == "__main__":
    unittest.main()
