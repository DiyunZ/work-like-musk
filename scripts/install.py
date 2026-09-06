#!/usr/bin/env python3
"""Install the local HUD into an existing work-like-musk skill, with backups."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- five-step-hud:start -->"
END = "<!-- five-step-hud:end -->"
LANGUAGES = ("en", "zh-CN")
LANGUAGE_CONFIG = "assets/hud-config.json"
SECTION = f"""{START}
## Optional Live Progress HUD

The HUD displays progress reported by the coach. On explicit project invocation,
HUD setup requests, or turns with an existing session, read
[the live progress guide](references/live-progress.md). Initialize/open this task's
own session when enabled and available; continue coaching if the HUD is unavailable
or the user opts out. Explain scoped checkpoints and evidence before stage reports;
keep the stage record and next move in the final response, even when commentary
collapses. Report actual stage events with the current revision.
By default, complete only the current stage and wait for the user's reply before
the next; continuous execution requires an explicit request. The guide supplies the confirmed-skip and
reopening protocol; display state does not decide the next project action.
Coach in the user's conversation language. Use English for new HUD report reasons
unless requested otherwise; preserve existing report text as recorded.
{END}"""
CHINESE_SECTION = f"""{START}
## 可选的实时进度 HUD

HUD 显示教练报告的实际进度。用户明确调用本 Skill 开展项目、要求配置 HUD，或当前
任务已有进度会话时，阅读[实时进度指南](references/live-progress.md)。启用且可用时，
为本任务独立初始化并打开会话；HUD 不可用或用户不希望启用时，继续提供指导。
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
    section = CHINESE_SECTION if language == "zh-CN" else SECTION
    if not re.match(r"\A---\r?\n[\s\S]*?^name:\s*[\"']?work-like-musk[\"']?\s*$[\s\S]*?^---\s*$", content, re.M):
        raise ValueError("Target must be an existing work-like-musk SKILL.md")
    if START not in content and END not in content:
        return content + ("\n" if content.endswith("\n") else "\n\n") + section + "\n"
    if content.count(START) != 1 or content.count(END) != 1 or content.index(END) < content.index(START):
        raise ValueError("Existing HUD managed section is malformed; preserve and inspect it first")
    begin, end = content.index(START), content.index(END) + len(END)
    return content[:begin] + section + content[end:]


def copy_item(source, target):
    # macOS ditto preserves resource forks, extended attributes and file modes.
    subprocess.run(["/usr/bin/ditto", str(source), str(target)], check=True, capture_output=True, text=True)


def remove_item(target):
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)


def install(skill, app, backup_root, language=None):
    skill = skill.expanduser().resolve(strict=True)
    entrypoint = skill / "SKILL.md"
    original_bytes = entrypoint.read_bytes()
    original = original_bytes.decode("utf-8")
    config_path = skill / LANGUAGE_CONFIG
    original_config = config_path.read_bytes() if config_path.exists() else None
    language = language if language is not None else (stored_language(skill) or "en")
    new_content = managed_entrypoint(original, language).encode("utf-8")
    if not (app / "Contents/MacOS/FiveStepHUD").is_file() or not (app / "Contents/Info.plist").is_file():
        raise ValueError("Build FiveStepHUD.app before installation")
    sources = {"scripts/five_step.py": ROOT / "skills/work-like-musk/scripts/five_step.py",
               "references/live-progress.md": ROOT / "skills/work-like-musk/references" / ("live-progress.zh-CN.md" if language == "zh-CN" else "live-progress.md"),
               "assets/FiveStepHUD.app": app.resolve()}
    generated = {"SKILL.md": new_content, LANGUAGE_CONFIG: (json.dumps({"language": language}) + "\n").encode("utf-8")}
    for source in sources.values():
        if not source.exists():
            raise ValueError(f"Missing source: {source}")
    backup_root = backup_root.expanduser().resolve()
    if backup_root == skill or skill in backup_root.parents:
        raise ValueError("Backups must be outside the skill directory")
    targets = {relative: (skill / relative).resolve() for relative in [*generated, *sources]}
    if len(set(targets.values())) != len(targets):
        raise ValueError("Install targets must be distinct")
    backup_root.mkdir(parents=True, exist_ok=True)
    lock_name = hashlib.sha256(str(skill).encode()).hexdigest() + ".lock"
    with (backup_root / lock_name).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another HUD installation owns this skill") from error
        for manifest_path in backup_root.glob("*/manifest.json"):
            previous = json.loads(manifest_path.read_text())
            if previous.get("skillPath") == str(skill) and previous.get("status") == "installing":
                raise ValueError(f"An unfinished installation needs inspection: {manifest_path}")
        if entrypoint.read_bytes() != original_bytes:
            raise ValueError("Skill changed during preflight; retry after the other writer finishes")
        if (config_path.read_bytes() if config_path.exists() else None) != original_config:
            raise ValueError("Language configuration changed during preflight; retry after the other writer finishes")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=backup_root))
        manifest = {"skillPath": str(skill), "status": "installing", "targets": {}}
        staged = {}
        applied = []
        staging_dirs = []
        try:
            for relative, target in targets.items():
                existed = target.exists()
                manifest["targets"][relative] = {"resolvedPath": str(target), "existed": existed}
                if existed:
                    saved = backup / relative
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    copy_item(target, saved)
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
            (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            # Publish the entrypoint last, after all referenced support files exist.
            for relative in [LANGUAGE_CONFIG, *sources, "SKILL.md"]:
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
            (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            for staging_dir in staging_dirs:
                shutil.rmtree(staging_dir)
    return {"skillPath": str(skill), "backupPath": str(backup), "appPath": str(targets["assets/FiveStepHUD.app"]), "language": language}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=Path.home() / ".codex/skills/work-like-musk")
    parser.add_argument("--app", type=Path, default=ROOT / "dist/FiveStepHUD.app")
    parser.add_argument("--backup-root", type=Path, default=Path.home() / ".codex/skill-backups/work-like-musk-hud")
    parser.add_argument("--language", choices=LANGUAGES, help="Interface and guidance language: en / zh-CN; prompts in a terminal, preserves an existing choice otherwise")
    args = parser.parse_args()
    try:
        language = choose_language(args.skill, args.language)
        print(json.dumps(install(args.skill, args.app, args.backup_root, language=language)))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"five-step install: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
