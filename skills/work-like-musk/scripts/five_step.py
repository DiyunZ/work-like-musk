#!/usr/bin/env python3
"""Report evidence-based five-step progress to a local macOS HUD."""

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid


STAGES = ("question", "delete", "simplify", "accelerate", "automate")
STATUSES = ("pending", "in_progress", "completed", "skipped", "blocked")
TERMINAL = ("completed", "skipped")
ACTIVE = ("in_progress", "blocked")
MAX_BYTES = 65536


def check_runtime_path(path):
    if path.parent.resolve() != path.parent:
        raise ValueError("Runtime directory must remain inside the canonical project without symlinks")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISREG(mode):
        raise ValueError(f"Runtime path must be a regular file: {path.name}")


def checked_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        raise ValueError(f"{label} must contain 1–{limit} characters without surrounding whitespace")
    return value


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def check_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        raise ValueError("Invalid UTC timestamp")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")


def pending(stage):
    return {"id": stage, "status": "pending", "reason": "", "updatedAt": None}


def validate(state, project, task):
    keys = {"schemaVersion", "projectPath", "taskId", "title", "revision", "updatedAt", "currentStage", "stages"}
    if not isinstance(state, dict) or set(state) != keys:
        raise ValueError("Invalid state fields")
    if type(state["schemaVersion"]) is not int or state["schemaVersion"] != 1:
        raise ValueError("Unsupported schemaVersion")
    if state["projectPath"] != str(project) or state["taskId"] != task:
        raise ValueError("State does not belong to this project and task")
    checked_text(state["taskId"], "Task ID", 200)
    checked_text(state["title"], "Title", 120)
    if type(state["revision"]) is not int or state["revision"] < 1:
        raise ValueError("Revision must be a positive integer")
    check_timestamp(state["updatedAt"])
    stages = state["stages"]
    if not isinstance(stages, list) or len(stages) != len(STAGES):
        raise ValueError("Exactly five stages are required")
    active_count = 0
    all_pending = True
    for index, (stage, expected) in enumerate(zip(stages, STAGES)):
        if not isinstance(stage, dict) or set(stage) != {"id", "status", "reason", "updatedAt"}:
            raise ValueError("Invalid stage fields")
        if stage["id"] != expected or stage["status"] not in STATUSES:
            raise ValueError("Invalid stage order or status")
        if stage["status"] == "pending":
            if stage["reason"] != "" or stage["updatedAt"] is not None:
                raise ValueError("Pending stages must have an empty reason and no timestamp")
        else:
            all_pending = False
            checked_text(stage["reason"], "Reason", 300)
            check_timestamp(stage["updatedAt"])
            if any(previous["status"] not in TERMINAL for previous in stages[:index]):
                raise ValueError("Earlier stages must be completed or skipped")
        if stage["status"] in ACTIVE:
            active_count += 1
            if state["currentStage"] != expected:
                raise ValueError("Active stage must match currentStage")
    if active_count > 1:
        raise ValueError("Only one stage can be active or blocked")
    current = state["currentStage"]
    if all_pending:
        if current is not None:
            raise ValueError("An untouched session has no currentStage")
    elif current not in STAGES or stages[STAGES.index(current)]["status"] == "pending":
        raise ValueError("currentStage must identify a reported stage")
    elif stages[STAGES.index(current)]["updatedAt"] != state["updatedAt"]:
        raise ValueError("updatedAt must match the current stage timestamp")
    return state


def load(path, project, task):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("State file exceeds 64 KiB")
    return validate(json.loads(data), project, task)


def atomic_write(path, state):
    data = (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("State file exceeds 64 KiB")
    descriptor, temporary = tempfile.mkstemp(prefix=".progress-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def transition(state, stage_id, status, reason):
    checked_text(reason, "Reason", 300)
    index = STAGES.index(stage_id)
    previous = state["stages"][index]
    if any(stage["status"] not in TERMINAL for stage in state["stages"][:index]):
        raise ValueError("Complete or skip earlier stages first")
    if previous["status"] == status and previous["reason"] == reason:
        return state
    if status == "completed" and previous["status"] not in ACTIVE:
        raise ValueError("Start or block a stage before completing it")
    updated = copy.deepcopy(state)
    now = timestamp()
    updated["stages"][index] = {"id": stage_id, "status": status, "reason": reason, "updatedAt": now}
    if status in ACTIVE:
        updated["stages"][index + 1:] = [pending(stage) for stage in STAGES[index + 1:]]
    updated.update(currentStage=stage_id, revision=state["revision"] + 1, updatedAt=now)
    return updated


def check_revision(state, expected):
    if expected != state["revision"]:
        raise ValueError("Session revision changed; read the current task again before reporting")


def request_skip(state, stage_id, target, reason):
    checked_text(reason, "Ordering reminder", 300)
    index, target_index = STAGES.index(stage_id), STAGES.index(target)
    if target_index <= index:
        raise ValueError("The skip target must be a later stage")
    if any(stage["status"] not in TERMINAL for stage in state["stages"][:index]):
        raise ValueError("Start the skip request at the first unfinished stage")
    if any(stage["status"] in TERMINAL for stage in state["stages"][index:target_index]):
        raise ValueError("Only unfinished stages can be requested for skipping")
    return {"taskId": state["taskId"], "projectPath": state["projectPath"], "revision": state["revision"],
            "requestId": str(uuid.uuid4()), "stage": stage_id, "target": target,
            "reason": reason, "requestedAt": timestamp()}


def load_skip_request(request_path):
    with request_path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Skip request exceeds 64 KiB")
    request = json.loads(data)
    keys = {"taskId", "projectPath", "revision", "requestId", "stage", "target", "reason", "requestedAt"}
    if not isinstance(request, dict) or set(request) != keys:
        raise ValueError("Invalid skip request; preserve and inspect it")
    checked_text(request["taskId"], "Skip task ID", 200)
    checked_text(request["reason"], "Ordering reminder", 300)
    checked_text(request["requestId"], "Skip request ID", 200)
    if not isinstance(request["projectPath"], str) or not Path(request["projectPath"]).is_absolute():
        raise ValueError("Invalid skip project path")
    if request["stage"] not in STAGES or request["target"] not in STAGES:
        raise ValueError("Invalid skip stage or target")
    if type(request["revision"]) is not int or request["revision"] < 1:
        raise ValueError("Invalid skip request revision")
    check_timestamp(request["requestedAt"])
    return request


def confirm_skip(state, request_path, request_id, reason):
    checked_text(reason, "User confirmation", 300)
    request = load_skip_request(request_path)
    if (request["taskId"], request["projectPath"], request["requestId"]) != (state["taskId"], state["projectPath"], request_id):
        raise ValueError("Skip confirmation does not belong to this task and request")
    check_revision(state, request["revision"])
    # Revalidate the frontier against the current state; a reopened step makes
    # the earlier request stale and cannot reuse its confirmation.
    request_skip(state, request["stage"], request["target"], request["reason"])
    for stage in STAGES[STAGES.index(request["stage"]):STAGES.index(request["target"])]:
        state = transition(state, stage, "skipped", reason)
    return state


def open_hud(path):
    root = Path(__file__).resolve().parents[1]
    app = next((root / folder / "FiveStepHUD.app" for folder in ("assets", "dist")
                if (root / folder / "FiveStepHUD.app/Contents/MacOS/FiveStepHUD").is_file()), None)
    if app is None:
        raise ValueError("FiveStepHUD.app is missing; build and install it first (state is preserved)")
    result = subprocess.run(["/usr/bin/open", "-g", "-a", str(app), str(path)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Could not open the HUD (state is preserved): {result.stderr.strip()}")


def parser():
    command_parser = argparse.ArgumentParser(description=__doc__)
    subcommands = command_parser.add_subparsers(dest="command", required=True)
    for command in ("setup", "update", "show", "open", "request-skip", "confirm-skip"):
        sub = subcommands.add_parser(command)
        sub.add_argument("--project", default=os.getcwd(), help="Project directory (default: current directory)")
        sub.add_argument("--task", default=os.environ.get("CODEX_THREAD_ID"), help="Task ID (default: CODEX_THREAD_ID)")
        if command == "setup":
            sub.add_argument("--title", help="Task title (default: task ID; existing titles are preserved)")
            sub.add_argument("--no-open", action="store_true", help="Create/validate state without opening the HUD")
        if command == "update":
            sub.add_argument("--stage", choices=STAGES, required=True)
            sub.add_argument("--status", choices=STATUSES[1:], required=True)
            sub.add_argument("--reason", required=True, help="Brief evidence for the change (1–300 characters)")
        if command in ("update", "request-skip", "confirm-skip"):
            sub.add_argument("--expected-revision", type=int, required=True,
                             help="Revision returned by show; rejects reports based on superseded work")
        if command == "request-skip":
            sub.add_argument("--stage", choices=STAGES, required=True)
            sub.add_argument("--to", choices=STAGES, required=True)
            sub.add_argument("--reason", required=True, help="The ordering reminder presented to the user")
        if command == "confirm-skip":
            sub.add_argument("--request-id", required=True)
            sub.add_argument("--reason", required=True, help="Evidence of the user's confirmation after the reminder")
    return command_parser


def main():
    command_parser = parser()
    args = command_parser.parse_args()
    try:
        task = checked_text(args.task, "Task ID (--task or CODEX_THREAD_ID)", 200)
        project = Path(args.project).expanduser().resolve(strict=True)
        if not project.is_dir():
            raise ValueError("Project must be an existing directory")
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        path = project / ".work-like-musk/sessions" / (digest + ".json")
        request_path = path.with_suffix(".skip.json")
        lock_path = path.with_suffix(".lock")
        for runtime_path in (path, request_path, lock_path):
            check_runtime_path(runtime_path)
        skip_request = None
        if args.command == "setup":
            title = checked_text(args.title if args.title is not None else task[:120], "Title", 120)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        elif not path.is_file():
            raise ValueError("This task has no session; run setup first")
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if path.exists():
                state = load(path, project, task)
            elif args.command == "setup":
                state = {"schemaVersion": 1, "projectPath": str(project), "taskId": task, "title": title,
                         "revision": 1, "updatedAt": timestamp(), "currentStage": None,
                         "stages": [pending(stage) for stage in STAGES]}
                atomic_write(path, state)
            else:
                raise ValueError("Session is missing; run setup first")
            if args.command == "update":
                if args.status == "skipped":
                    raise ValueError("Use request-skip to explain the order, then confirm-skip only after the user confirms")
                previous = state["stages"][STAGES.index(args.stage)]
                if (previous["status"], previous["reason"]) != (args.status, args.reason):
                    check_revision(state, args.expected_revision)
                updated = transition(state, args.stage, args.status, args.reason)
                validate(updated, project, task)
                if updated != state:
                    atomic_write(path, updated)
                    state = updated
            elif args.command == "request-skip":
                check_revision(state, args.expected_revision)
                skip_request = request_skip(state, args.stage, args.to, args.reason)
                prior_request = load_skip_request(request_path) if request_path.exists() else None
                if prior_request is not None:
                    if (prior_request["taskId"], prior_request["projectPath"]) != (task, str(project)):
                        raise ValueError("Skip request belongs to another task; preserve and inspect it")
                    if all(prior_request[key] == skip_request[key] for key in ("revision", "stage", "target", "reason")):
                        skip_request = prior_request
                if skip_request != prior_request:
                    atomic_write(request_path, skip_request)
            elif args.command == "confirm-skip":
                check_revision(state, args.expected_revision)
                updated = confirm_skip(state, request_path, args.request_id, args.reason)
                validate(updated, project, task)
                atomic_write(path, updated)
                state = updated
        if args.command == "open" or (args.command == "setup" and not args.no_open):
            open_hud(path)
        if args.command == "show":
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            current = state["currentStage"]
            result = {"statePath": str(path), "revision": state["revision"], "currentStage": current,
                      "status": state["stages"][STAGES.index(current)]["status"] if current else "pending"}
            if skip_request is not None:
                result["skipRequest"] = skip_request
            print(json.dumps(result))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"five-step: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
