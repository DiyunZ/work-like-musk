#!/usr/bin/env python3
"""Install Work Like Musk and its integrated HUD for local Agent Skills hosts."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/work-like-musk/scripts"))
from runtime_support import file_lock

START = "<!-- five-step-hud:start -->"
END = "<!-- five-step-hud:end -->"
LANGUAGES = ("en", "zh-CN")
LANGUAGE_CONFIG = "assets/hud-config.json"
RUNTIME_CONFIG = "assets/runtime-config.json"
PORTABLE_RUNTIME_CONFIG = "assets/portable-runtime.json"
QT_PROBE = ("import PySide6\nfrom PySide6.QtWidgets import QApplication\n"
            "version = tuple(int(part) for part in PySide6.__version__.split('.')[:2])\n"
            "if not (6, 8) <= version < (7, 0): raise RuntimeError('PySide6 >=6.8,<7 is required')\n")
LEGACY_DESCRIPTION = ('description: "Use for project coaching with an integrated live progress HUD in local Codex on macOS 14+, '
                      'or when continuing a project already using Work Like Musk. Keep factual questions and straightforward '
                      'edits scoped to their immediate purpose."')
AGENT_DIRECTORIES = {
    "codex": ".codex/skills/work-like-musk",
    "claude-code": ".claude/skills/work-like-musk",
    "cursor": ".cursor/skills/work-like-musk",
    "gemini-cli": ".gemini/skills/work-like-musk",
    "opencode": ".config/opencode/skills/work-like-musk",
    "generic": ".agents/skills/work-like-musk",
}
CHINESE_SECTION = f"""{START}
## 一体化实时进度 HUD

Work Like Musk 将项目指导与实时进度 HUD 整合为同一产品，支持 Windows、Linux 桌面
和 macOS 上能够加载 Agent Skills 并运行 Python 的本地 agent。调用本 Skill 开展项目或已有进度会话时，阅读
[实时进度指南](references/live-progress.md)，检查安装，为本任务独立初始化并打开会话。
从当前加载的 Skill 解析路径，使用已安装的显示方式，保留本对话的真实宿主 ID 或初始化返回的跟踪 ID。
通用悬浮窗明确显示绑定任务；macOS 14+ 的 Codex 仍可使用原生标题跟随。
HUD 是标准工作流程的一部分。缺少运行文件、Qt、图形桌面或配置失败意味着产品尚未配置完整：
说明具体问题，在已有授权内修复，不静默改用纯文字指导，也不宣称 HUD 已就绪。
配置受阻期间可以继续不依赖它的检查工作。
报告阶段前先说明对应范围的验收条件和证据；最终回复保留阶段记录及下一步，
不依赖可能折叠的过程消息。携带当前修订号报告实际阶段变化。
默认每完成一步都等待用户回应，下一步保持待开始；只有用户明确要求时才跨步骤持续执行。
指南规定跳步确认和重开的协议，
显示状态不决定项目下一步该做什么。
使用用户的对话语言提供指导；除非另有要求，新的 HUD 说明使用简体中文。
保留已有记录的原文，命令参数和状态标识仍使用固定英文值。
{END}"""


def stored_language(skill):
    config = skill.expanduser() / LANGUAGE_CONFIG
    if not config.exists():
        return None
    try:
        data = json.loads(config.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid HUD language configuration; choose --language en or --language zh-CN to replace it") from error
    if not isinstance(data, dict) or set(data) != {"language"} or data["language"] not in LANGUAGES:
        raise ValueError("Unsupported HUD language configuration; choose --language en or --language zh-CN to replace it")
    return data["language"]


def default_skill(agent):
    if agent == "opencode" and os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).expanduser() / "opencode/skills/work-like-musk"
    return Path.home() / AGENT_DIRECTORIES[agent]


def stored_runtime(skill):
    config = skill.expanduser() / RUNTIME_CONFIG
    if not config.exists():
        return None
    data = json.loads(config.read_bytes())
    if (not isinstance(data, dict) or set(data) != {"schemaVersion", "agent", "backend"}
            or type(data["schemaVersion"]) is not int or data["schemaVersion"] != 1
            or data["agent"] not in AGENT_DIRECTORIES or data["backend"] not in ("native", "portable")):
        raise ValueError("Invalid HUD runtime configuration; specify --agent and --hud to replace it")
    return data


def portable_runtime_error(python):
    try:
        result = subprocess.run([str(python), "-c", QT_PROBE], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        return str(error)
    if result.returncode:
        return (result.stderr or result.stdout or f"Qt probe exited with status {result.returncode}").strip()
    return None


def ensure_portable_runtime():
    # Resolving a venv's executable symlink would discard its installed packages.
    current = Path(sys.executable).absolute()
    if portable_runtime_error(current) is None:
        return current
    runtimes = (Path.home() / ".work-like-musk/runtimes").resolve()
    name = f"pyside6-py{sys.version_info.major}.{sys.version_info.minor}"
    environment = runtimes / name
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    state_path = runtimes / (name + ".json")
    lock_path = runtimes / (name + ".lock")
    runtimes.mkdir(parents=True, exist_ok=True)
    if (environment.is_symlink() or (environment.exists() and not environment.is_dir())
            or any(path.is_symlink() or (path.exists() and not path.is_file()) for path in (state_path, lock_path))):
        raise ValueError(f"Qt runtime needs inspection: {environment}")
    try:
        with lock_path.open("a+b") as lock, file_lock(lock, blocking=False):
            previous = None
            if state_path.exists():
                try:
                    previous = json.loads(state_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise ValueError(f"Qt runtime record needs inspection: {state_path}") from error
                if (not isinstance(previous, dict) or set(previous) != {"schemaVersion", "pythonExecutable", "status"}
                        or type(previous["schemaVersion"]) is not int or previous["schemaVersion"] != 1
                        or previous["pythonExecutable"] != str(python)
                        or previous["status"] not in ("provisioning", "ready", "failed")):
                    raise ValueError(f"Qt runtime record needs inspection: {state_path}")
                if previous["status"] == "provisioning":
                    raise ValueError(f"Unfinished Qt runtime setup needs inspection: {state_path}")
            elif environment.exists():
                raise ValueError(f"Existing Qt runtime has no ownership record; needs inspection: {environment}")
            if previous is not None and previous["status"] == "ready" and portable_runtime_error(python) is None:
                return python
            state = {"schemaVersion": 1, "pythonExecutable": str(python), "status": "provisioning"}
            write_json(state_path, state)
            print(f"Preparing private Qt runtime: {environment}", file=sys.stderr, flush=True)
            try:
                commands = []
                if not python.is_file() or not (environment / "pyvenv.cfg").is_file():
                    commands.append([str(current), "-m", "venv", str(environment)])
                commands.append([str(python), "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
                                 "--no-input", "--index-url", "https://pypi.org/simple", "PySide6-Essentials>=6.8,<7"])
                for command in commands:
                    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                            errors="replace", timeout=300)
                    if result.returncode:
                        raise ValueError((result.stderr or result.stdout or f"Command exited with status {result.returncode}").strip())
                error = portable_runtime_error(python)
                if error is not None:
                    raise ValueError(error)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                state["status"] = "failed"
                write_json(state_path, state)
                raise ValueError(f"Qt runtime setup failed in {environment}: {error}") from error
            state["status"] = "ready"
            write_json(state_path, state)
            return python
    except BlockingIOError as error:
        raise ValueError(f"Qt runtime setup is already running; retry after it finishes: {environment}") from error


def choose_language(skill, requested):
    if requested is not None:
        return requested
    previous = stored_language(skill)
    if not sys.stdin.isatty():
        if previous is not None:
            return previous
        raise ValueError("Choose --language zh-CN (中文) or --language en (English) for a non-interactive first install")
    default = previous or "en"
    while True:
        print(f"选择安装语言 / Choose installation language: 1 中文, 2 English [default: {default}]: ",
              end="", file=sys.stderr, flush=True)
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt) as error:
            raise ValueError("Installation cancelled / 已取消安装") from error
        choices = {"": default, "1": "zh-CN", "zh-cn": "zh-CN", "中文": "zh-CN", "2": "en", "en": "en", "english": "en"}
        if answer in choices:
            return choices[answer]
        print("请输入 1 或 2 / Enter 1 or 2.", file=sys.stderr)


def managed_entrypoint(content, language="en"):
    if language not in LANGUAGES:
        raise ValueError("Language must be en or zh-CN")
    stock = (ROOT / "skills/work-like-musk/SKILL.md").read_text(encoding="utf-8")
    section = CHINESE_SECTION if language == "zh-CN" else stock[stock.index(START):stock.index(END) + len(END)]
    frontmatter = re.match(r"\A---\r?\n[\s\S]*?^name:\s*[\"']?work-like-musk[\"']?\s*$[\s\S]*?^---\s*$", content, re.M)
    if not frontmatter:
        raise ValueError("Target must be an existing work-like-musk SKILL.md")
    description = re.search(r"^description:[^\r\n]*", frontmatter.group(), re.M)
    if description is not None and description.group() == LEGACY_DESCRIPTION:
        current = re.search(r"^description:[^\r\n]*", stock, re.M).group()
        content = content[:description.start()] + current + content[description.end():]
    if START not in content and END not in content:
        return content + ("\n" if content.endswith("\n") else "\n\n") + section + "\n"
    if content.count(START) != 1 or content.count(END) != 1 or content.index(END) < content.index(START):
        raise ValueError("Existing HUD managed section is malformed; preserve and inspect it first")
    begin, end = content.index(START), content.index(END) + len(END)
    return content[:begin] + section + content[end:]


def copy_item(source, target):
    if sys.platform == "darwin":
        # Keep macOS resource forks, extended attributes and file modes.
        subprocess.run(["/usr/bin/ditto", str(source), str(target)], check=True, capture_output=True, text=True)
    elif source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)


def remove_item(target):
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)


def write_json(path, value):
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Windows reports open-reader replacement failures as either access
        # denied (5) or sharing violation (32). Persistent errors still fail.
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except OSError as error:
                if sys.platform != "win32" or getattr(error, "winerror", None) not in (5, 32) or attempt == 4:
                    raise
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def install(skill, app, backup_root, language=None, agent="codex", backend="native"):
    if agent not in AGENT_DIRECTORIES or backend not in ("native", "portable"):
        raise ValueError("Choose a supported agent and HUD backend")
    skill = skill.expanduser()
    if skill.is_symlink() and not skill.exists():
        raise ValueError("The skill directory is a broken link; preserve and inspect it first")
    skill = skill.resolve()
    existed_before = skill.exists()
    entrypoint = skill / "SKILL.md"
    if existed_before and not entrypoint.is_file():
        raise ValueError("Existing directory is not a work-like-musk installation; preserve and inspect it first")
    source_skill = ROOT / "skills/work-like-musk"
    original_bytes = entrypoint.read_bytes() if existed_before else None
    original = (original_bytes if original_bytes is not None else (source_skill / "SKILL.md").read_bytes()).decode("utf-8")
    config_path = skill / LANGUAGE_CONFIG
    original_config = config_path.read_bytes() if config_path.exists() else None
    language = language if language is not None else (stored_language(skill) or "en")
    new_content = managed_entrypoint(original, language).encode("utf-8")
    if backend == "native" and (app is None or not (app / "Contents/MacOS/FiveStepHUD").is_file()
                                or not (app / "Contents/Info.plist").is_file()):
        raise ValueError("Build FiveStepHUD.app before installation")
    sources = {"scripts/five_step.py": ROOT / "skills/work-like-musk/scripts/five_step.py",
               "scripts/runtime_support.py": source_skill / "scripts/runtime_support.py",
               "scripts/portable_hud.py": source_skill / "scripts/portable_hud.py",
               "references/live-progress.md": ROOT / "skills/work-like-musk/references" / ("live-progress.zh-CN.md" if language == "zh-CN" else "live-progress.md"),
               "references/live-progress.zh-CN.md": source_skill / "references/live-progress.zh-CN.md"}
    if backend == "native":
        sources["assets/FiveStepHUD.app"] = app.resolve()
    if not (skill / "agents/openai.yaml").exists():
        sources["agents/openai.yaml"] = source_skill / "agents/openai.yaml"
    generated = {
        "SKILL.md": new_content,
        LANGUAGE_CONFIG: (json.dumps({"language": language}) + "\n").encode("utf-8"),
        RUNTIME_CONFIG: (json.dumps({"schemaVersion": 1, "agent": agent, "backend": backend}) + "\n").encode("utf-8"),
    }
    portable_path = skill / PORTABLE_RUNTIME_CONFIG
    original_portable = portable_path.read_bytes() if backend == "portable" and portable_path.exists() else None
    if backend == "portable":
        generated[PORTABLE_RUNTIME_CONFIG] = b""  # Filled after ownership and dependency checks.
    original_runtime = (skill / RUNTIME_CONFIG).read_bytes() if (skill / RUNTIME_CONFIG).exists() else None
    for source in sources.values():
        if not source.exists():
            raise ValueError(f"Missing source: {source}")
    backup_root = backup_root.expanduser().resolve()
    if backup_root == skill or skill in backup_root.parents:
        raise ValueError("Backups must be outside the skill directory")
    targets = {relative: (skill / relative).resolve() for relative in [*generated, *sources]}
    if len(set(targets.values())) != len(targets):
        raise ValueError("Install targets must be distinct")
    coordination = skill.parent / ".work-like-musk-installations"
    coordination.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(skill).encode()).hexdigest()
    transaction_path = coordination / (identity + ".json")
    with (coordination / (identity + ".lock")).open("a+b") as lock, file_lock(lock, blocking=False):
        if transaction_path.exists():
            transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
            if (not isinstance(transaction, dict) or transaction.get("skillPath") != str(skill)
                    or not isinstance(transaction.get("manifestPath"), str)
                    or not Path(transaction["manifestPath"]).is_absolute()):
                raise ValueError(f"Installation transaction needs inspection: {transaction_path}")
            manifest_path = Path(transaction["manifestPath"])
            try:
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise ValueError(f"Installation transaction needs inspection: {manifest_path}") from error
            if (not isinstance(previous, dict) or previous.get("skillPath") != str(skill)
                    or previous.get("status") not in ("installing", "installed", "rolled_back")):
                raise ValueError(f"Installation transaction needs inspection: {manifest_path}")
            if previous["status"] == "installing":
                raise ValueError(f"An unfinished installation needs inspection: {manifest_path}")
        legacy_roots = {backup_root, (Path.home() / ".codex/skill-backups/work-like-musk-hud").resolve(),
                        (Path.home() / ".work-like-musk/skill-backups").resolve()}
        for legacy_root in legacy_roots:
            for manifest_path in legacy_root.glob("*/manifest.json"):
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                if previous.get("skillPath") == str(skill) and previous.get("status") == "installing":
                    raise ValueError(f"An unfinished installation needs inspection: {manifest_path}")
        def check_preflight():
            if (entrypoint.read_bytes() if entrypoint.exists() else None) != original_bytes:
                raise ValueError("Skill changed during preflight; retry after the other writer finishes")
            if not existed_before and skill.exists():
                raise ValueError("The skill directory appeared during preflight; inspect the other writer's work")
            if (config_path.read_bytes() if config_path.exists() else None) != original_config:
                raise ValueError("Language configuration changed during preflight; retry after the other writer finishes")
            runtime_path = skill / RUNTIME_CONFIG
            if (runtime_path.read_bytes() if runtime_path.exists() else None) != original_runtime:
                raise ValueError("HUD runtime configuration changed during preflight; retry after the other writer finishes")
            if backend == "portable" and (portable_path.read_bytes() if portable_path.exists() else None) != original_portable:
                raise ValueError("Portable runtime configuration changed during preflight; retry after the other writer finishes")

        check_preflight()
        if backend == "portable":
            python = ensure_portable_runtime()
            check_preflight()
            generated[PORTABLE_RUNTIME_CONFIG] = (json.dumps({"schemaVersion": 1, "pythonExecutable": str(python)}) + "\n").encode("utf-8")
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=backup_root))
        manifest_path = backup / "manifest.json"
        manifest = {"skillPath": str(skill), "status": "installing", "targets": {
            relative: {"resolvedPath": str(target), "existed": target.exists()} for relative, target in targets.items()}}
        staged = {}
        applied = []
        staging_dirs = []
        created_dirs = set()
        try:
            write_json(manifest_path, manifest)
            # Register ownership before creating staging directories or changing skill files.
            write_json(transaction_path, {"skillPath": str(skill), "manifestPath": str(manifest_path)})
            for relative, target in targets.items():
                existed = manifest["targets"][relative]["existed"]
                if existed:
                    saved = backup / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    copy_item(target, saved)
                parent = target.parent
                while not parent.exists():
                    created_dirs.add(parent)
                    parent = parent.parent
                target.parent.mkdir(parents=True, exist_ok=True)
                staging_dir = Path(tempfile.mkdtemp(prefix=".five-step-install-", dir=target.parent))
                staging_dirs.append(staging_dir)
                stage = staging_dir / target.name
                if relative in generated:
                    if existed:
                        copy_item(target, stage)
                    stage.write_bytes(generated[relative])
                else:
                    if existed and target.is_file():
                        copy_item(target, stage)
                        stage.write_bytes(sources[relative].read_bytes())
                    else:
                        copy_item(sources[relative], stage)
                staged[relative] = stage
            # Publish the entrypoint last, after all referenced support files exist.
            for relative in [*[relative for relative in generated if relative != "SKILL.md"], *sources, "SKILL.md"]:
                target = targets[relative]
                applied.append(relative)
                if target.is_dir():
                    os.replace(target, staged[relative].parent / "previous")
                os.replace(staged[relative], target)
            manifest["status"] = "installed"
        except Exception:
            for relative in reversed(applied):
                target = targets[relative]
                remove_item(target)
                if manifest["targets"][relative]["existed"]:
                    copy_item(backup / relative, target)
            manifest["status"] = "rolled_back"
            raise
        finally:
            write_json(manifest_path, manifest)
            if manifest["status"] in ("installed", "rolled_back"):
                transaction_path.unlink(missing_ok=True)
            for staging_dir in staging_dirs:
                shutil.rmtree(staging_dir)
            if manifest["status"] == "rolled_back":
                for directory in sorted(created_dirs, key=lambda item: len(item.parts), reverse=True):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass  # Preserve anything another writer placed here.
    app_path = str(targets["assets/FiveStepHUD.app"]) if backend == "native" else None
    return {"skillPath": str(skill), "backupPath": str(backup), "appPath": app_path,
            "hudPath": app_path or str(targets["scripts/portable_hud.py"]),
            "language": language, "agent": agent, "backend": backend}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=tuple(AGENT_DIRECTORIES), help="Agent to install for (default: codex, or the saved agent for --skill)")
    parser.add_argument("--skill", type=Path, help="Exact skill directory; otherwise use the selected agent's personal location")
    parser.add_argument("--hud", choices=("auto", "native", "portable"), default="auto", help="HUD display: native for macOS/Codex, portable elsewhere; preserves an existing choice")
    parser.add_argument("--app", type=Path, help="Use an already built HUD; otherwise build the bundled native source")
    parser.add_argument("--backup-root", type=Path, help="Backup directory; defaults to the existing Codex backup location or ~/.work-like-musk/skill-backups")
    parser.add_argument("--language", choices=LANGUAGES, help="Interface and guidance language: en / zh-CN; prompts in a terminal, preserves an existing choice otherwise")
    args = parser.parse_args()
    try:
        if sys.platform not in ("darwin", "win32", "linux"):
            raise ValueError("Work Like Musk supports Windows, Linux desktops, and macOS")
        agent = args.agent or "codex"
        skill = args.skill or default_skill(agent)
        try:
            saved = stored_runtime(skill)
        except ValueError:
            if args.agent is None or args.hud == "auto":
                raise
            saved = None
        if args.agent is None and saved is not None:
            agent = saved["agent"]
        native_supported = sys.platform == "darwin" and int(platform.mac_ver()[0].split(".")[0]) >= 14
        backend = args.hud
        if backend == "auto":
            if args.app is not None:
                backend = "native"
            elif saved is not None and saved["agent"] == agent:
                backend = saved["backend"]
            else:
                backend = "native" if native_supported and agent == "codex" else "portable"
        if backend == "native" and (not native_supported or agent != "codex"):
            raise ValueError("Native title tracking requires Codex on macOS 14+; use --hud portable for this environment")
        if backend == "portable" and args.app is not None:
            raise ValueError("--app selects a native app and cannot be combined with --hud portable")
        language = choose_language(skill, args.language)
        backup_root = args.backup_root or Path.home() / (
            ".codex/skill-backups/work-like-musk-hud" if agent == "codex" else ".work-like-musk/skill-backups")
        app = args.app
        if backend == "native" and app is None:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/build.py")], capture_output=True, text=True)
            if result.stdout:
                print(result.stdout.rstrip(), file=sys.stderr)
            if result.stderr:
                print(result.stderr.rstrip(), file=sys.stderr)
            result.check_returncode()
            app = ROOT / "dist/FiveStepHUD.app"
        print(json.dumps(install(skill, app, backup_root, language=language, agent=agent, backend=backend)))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"five-step install: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
