#!/usr/bin/env python3
"""Install the Work Like Musk coaching skill for an Agent Skills host."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- five-step-hud:start -->"
END = "<!-- five-step-hud:end -->"
# Upgrade cleanup only: none of these files is installed by this version.
LEGACY_FILES = (
    "scripts/five_step.py",
    "scripts/runtime_support.py",
    "scripts/portable_hud.py",
    "references/live-progress.md",
    "references/live-progress.zh-CN.md",
    "assets/FiveStepHUD.app",
    "assets/hud-config.json",
    "assets/runtime-config.json",
    "assets/portable-runtime.json",
)
AGENT_DIRECTORIES = {
    "codex": ".codex/skills/work-like-musk",
    "claude-code": ".claude/skills/work-like-musk",
    "cursor": ".cursor/skills/work-like-musk",
    "gemini-cli": ".gemini/skills/work-like-musk",
    "opencode": ".config/opencode/skills/work-like-musk",
    "generic": ".agents/skills/work-like-musk",
}
LEGACY_DESCRIPTIONS = tuple(
    'description: "Use for project coaching with an integrated live progress HUD in '
    + environment
    + ', or when continuing a project already using Work Like Musk. '
    'Keep factual questions and straightforward edits scoped to their immediate purpose."'
    for environment in ("local Codex on macOS 14+", "local AI agents on Windows, Linux, or macOS")
)
COACHING_REPLACEMENTS = {
    "At entry, state what the five indicators track: the user's requested outcome":
        "At entry, state the user's requested outcome",
    "Then report the HUD event. The HUD follows these explanations; tool arguments, hover text and silent internal decisions do not supply them.":
        "Keep these explanations in the conversation.",
    "do not run ceremonial start/complete reports to fill all five indicators.":
        "do not report ceremonial completions to fill all five stages.",
}
METADATA_REPLACEMENTS = {
    "Five-step project coaching with an integrated progress HUD":
        "Five-step project coaching with advice and evidence",
    "Use $work-like-musk to start the integrated progress HUD and coach":
        "Use $work-like-musk to coach",
}


@contextmanager
def file_lock(stream):
    """Hold a nonblocking OS lock throughout an installation transaction."""
    if os.name == "nt":
        import errno
        import msvcrt
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError(error.errno, "Installation is already running") from error
            raise
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def default_skill(agent):
    if agent == "opencode" and os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).expanduser() / "opencode/skills/work-like-musk"
    return Path.home() / AGENT_DIRECTORIES[agent]


def managed_entrypoint(content):
    frontmatter = re.match(r"\A---\r?\n[\s\S]*?^name:\s*[\"']?(?:work-like-musk|musk-five-step)[\"']?\s*$[\s\S]*?^---\s*$", content, re.M)
    if not frontmatter:
        raise ValueError("Target must be a work-like-musk or legacy musk-five-step SKILL.md")
    description = re.search(r"^description:[^\r\n]*", frontmatter.group(), re.M)
    if description is not None and description.group() in LEGACY_DESCRIPTIONS:
        stock = (ROOT / "skills/work-like-musk/SKILL.md").read_text(encoding="utf-8")
        current = re.search(r"^description:[^\r\n]*", stock, re.M).group()
        content = content[:description.start()] + current + content[description.end():]
    if START in content or END in content:
        if content.count(START) != 1 or content.count(END) != 1 or content.index(END) < content.index(START):
            raise ValueError("Existing HUD managed section is malformed; preserve and inspect it first")
        begin, end = content.index(START), content.index(END) + len(END)
        if content[end:].startswith("\r\n"):
            end += 2
        elif content[end:].startswith("\n"):
            end += 1
        content = content[:begin] + content[end:]
    for old, new in COACHING_REPLACEMENTS.items():
        content = content.replace(old, new)
    return content


def copy_item(source, target):
    if source.is_symlink():
        target.symlink_to(os.readlink(source), target_is_directory=source.is_dir())
    elif sys.platform == "darwin":
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


def install(skill, backup_root):
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
    new_content = managed_entrypoint(original).encode("utf-8")
    metadata_path = skill / "agents/openai.yaml"
    if metadata_path.is_symlink() and not metadata_path.exists():
        raise ValueError("Agent metadata is a broken link; preserve and inspect it first")
    if metadata_path.exists() and not metadata_path.is_file():
        raise ValueError("Agent metadata must be a regular file")
    original_metadata = metadata_path.read_bytes() if metadata_path.exists() else None
    metadata = original_metadata if original_metadata is not None else (source_skill / "agents/openai.yaml").read_bytes()
    if original_metadata is None and re.search(r"^name:\s*[\"']?musk-five-step[\"']?\s*$", original, re.M):
        metadata = metadata.replace(b"$work-like-musk", b"$musk-five-step")
    for old, new in METADATA_REPLACEMENTS.items():
        metadata = metadata.replace(old.encode(), new.encode())
    generated = {"SKILL.md": new_content, "agents/openai.yaml": metadata}
    backup_root = backup_root.expanduser().resolve()
    if backup_root == skill or skill in backup_root.parents:
        raise ValueError("Backups must be outside the skill directory")
    targets = {relative: (skill / relative).resolve() for relative in generated}
    obsolete = {}
    for relative in LEGACY_FILES:
        target = skill / relative
        # Do not follow a shared support directory to delete someone else's files.
        if any(parent.is_symlink() for parent in target.parents if parent != skill and skill in parent.parents):
            raise ValueError(f"Legacy support directory is linked; preserve and inspect it first: {target.parent}")
        if target.exists() or target.is_symlink():
            if not (target.is_file() or target.is_dir() or target.is_symlink()):
                raise ValueError(f"Legacy file needs inspection: {target}")
            obsolete[relative] = target
    targets.update(obsolete)
    if len(set(targets.values())) != len(targets):
        raise ValueError("Install targets must be distinct")
    coordination = skill.parent / ".work-like-musk-installations"
    coordination.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(skill).encode()).hexdigest()
    transaction_path = coordination / (identity + ".json")
    with (coordination / (identity + ".lock")).open("a+b") as lock, file_lock(lock):
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
                        (Path.home() / ".codex/skill-backups/musk-five-step-hud").resolve(),
                        (Path.home() / ".work-like-musk/skill-backups").resolve()}
        for legacy_root in legacy_roots:
            for manifest_path in legacy_root.glob("*/manifest.json"):
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                if previous.get("skillPath") == str(skill) and previous.get("status") == "installing":
                    raise ValueError(f"An unfinished installation needs inspection: {manifest_path}")
        if (entrypoint.read_bytes() if entrypoint.exists() else None) != original_bytes:
            raise ValueError("Skill changed during preflight; retry after the other writer finishes")
        if not existed_before and skill.exists():
            raise ValueError("The skill directory appeared during preflight; inspect the other writer's work")
        if (metadata_path.read_bytes() if metadata_path.exists() else None) != original_metadata:
            raise ValueError("Agent metadata changed during preflight; retry after the other writer finishes")
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        backup = Path(tempfile.mkdtemp(prefix=stamp + "-", dir=backup_root))
        manifest_path = backup / "manifest.json"
        manifest = {"skillPath": str(skill), "status": "installing", "targets": {
            relative: {"resolvedPath": str(target), "existed": target.exists() or target.is_symlink(),
                       "action": "remove" if relative in obsolete else "replace"}
            for relative, target in targets.items()}}
        staged = {}
        applied = []
        staging_dirs = []
        created_dirs = set()
        try:
            write_json(manifest_path, manifest)
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
                staged[relative] = stage
            # Publish the new instructions before retiring their old dependencies.
            for relative in ["agents/openai.yaml", "SKILL.md", *obsolete]:
                target = targets[relative]
                applied.append(relative)
                if relative in obsolete:
                    os.replace(target, staged[relative])
                else:
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
        # Remove only empty former runtime folders; keep custom files and session data.
        for relative in ("scripts", "references", "assets"):
            try:
                (skill / relative).rmdir()
            except OSError:
                pass
    return {"skillPath": str(skill), "backupPath": str(backup), "removedFiles": list(obsolete)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=tuple(AGENT_DIRECTORIES), default="codex", help="Agent to install for (default: codex)")
    parser.add_argument("--skill", type=Path, help="Exact skill directory; otherwise use the selected agent's personal location")
    parser.add_argument("--backup-root", type=Path, help="Backup directory (default: ~/.work-like-musk/skill-backups)")
    args = parser.parse_args()
    try:
        skill = args.skill or default_skill(args.agent)
        backup_root = args.backup_root or Path.home() / ".work-like-musk/skill-backups"
        result = install(skill, backup_root)
        print(json.dumps({**result, "agent": args.agent}))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"work-like-musk install: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
