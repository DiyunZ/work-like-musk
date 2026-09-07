# Cross-platform HUD Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent implementation tasks; keep integration and review in this task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the complete coaching skill and an explicitly bound floating HUD across Windows, Linux, macOS, and local Agent Skills hosts.

**Architecture:** Preserve the state protocol and macOS title-following adapter. Add portable locking, explicit local tracking identities, a Qt floating window, and an installer that selects the agent location and HUD backend.

**Tech Stack:** Python 3.9+, Qt for Python 6.8+, existing SwiftUI/AppKit native HUD, unittest, GitHub Actions.

**Spec:** [Cross-platform integrated HUD](../specs/2026-09-06-cross-platform-hud-design.md).

## Global Constraints

- The HUD remains part of the product.
- Python 3.9+ is required; portable GUI startup requires Qt for Python 6.8+ and a graphical desktop.
- Native Codex mode requires macOS 14+ and Swift command-line tools.
- Default coaching completes one stage and waits for the user's reply.
- Preserve the existing state schema, revision checks, skip confirmation, rollback, and unrelated user customizations.
- Published illustrations and screenshots use English and synthetic, non-personal content.

## Task 1: Portable state and launch runtime

Files: create `skills/work-like-musk/scripts/runtime_support.py` and `tests/test_runtime.py`; modify `skills/work-like-musk/scripts/five_step.py` and `tests/test_progress.py`.

Produces: `file_lock(stream, blocking=True)`; `setup --new-task` returning `taskId`; bounded native/portable startup through the handshake described in the spec.

- [x] Add a subprocess test that invokes `setup --new-task --no-open` twice with no host ID and asserts distinct returned IDs and independent pending states.
- [x] Add tests that opening without a GUI or receiving an error from the portable launcher returns a concrete failure while preserving the state. Test the actual spawned child contract with a small fixture script.
- [x] Run the new tests and record the missing-capability failures.
- [x] Replace unconditional POSIX imports with the shared lock context manager; retain actual concurrent-writer tests.
- [x] Implement the identity and backend arguments, preserve literal subprocess arguments, and return startup observations separately from stage status.
- [x] Run `python3 -m unittest discover -s tests -p 'test_progress.py' -v` and the new runtime tests. Review the diff and commit this unit.

## Task 2: Complete installation across hosts

Files: modify `scripts/install.py` and `tests/test_install.py`.

Consumes: the shared lock context manager and bundled runtime scripts. Produces a complete installation with `assets/runtime-config.json` containing its agent and backend, alongside the existing language file.

- [x] Add fresh portable-install tests for each agent destination, no native app dependency, dependency-failure rollback, and preserved custom metadata.
- [x] Run the new tests and confirm current macOS-only installation fails them.
- [x] Add `--agent` and backend selection, platform-appropriate copying, and private Qt runtime preparation after ownership checks. Retain the native `--app` override.
- [x] Include the shared runtime and portable HUD files in the existing backed-up transaction; publish `SKILL.md` last.
- [x] Run installer regressions and inspect an actual fresh portable installation. Commit after review.

## Task 3: Standalone floating HUD

Files: create `skills/work-like-musk/scripts/portable_hud.py` and `tests/test_portable_hud.py`.

Consumes: the unchanged five-stage state schema, `five_step.load`, and `runtime_support.file_lock`. Produces a task-bound Qt window and the bounded launch handshake.

- [x] Write real Qt tests for pending readiness, first-stage completion, task identity mismatch, corrupt-state clearing, and two separate task windows.
- [x] Run them before implementation to record the missing HUD behavior.
- [x] Implement a compact movable floating window showing title, project, task identifier, stage symbols, and evidence on hover. Include English/Chinese labels and a motion toggle.
- [x] Bind the window to exactly the supplied task, acquire its HUD lock, and acknowledge startup only after window creation. Report errors without rewriting progress.
- [x] Run Qt tests on a real GUI runtime, inspect an English synthetic preview, review the component, and commit.

## Task 4: Host instructions, platform matrix, and release

Files: modify both README files, HUD guides, verification scope, skill entrypoint/references, agent metadata, `.github/workflows/checks.yml`, and the native app version.

Consumes: the complete portable installation and runtime from Tasks 1–3. Produces documented agent entry points, verified CI results for three operating systems, and a public release.

- [x] Replay the old instructions for Windows/Claude Code, Linux/Gemini CLI, and macOS/Cursor and record their unsupported-host behavior.
- [x] Update instructions to resolve the loaded skill directory, choose the installed display, and use a real session ID or explicit new tracking ID.
- [x] Preserve one-stage pauses and document that portable windows are bound to named tasks.
- [x] Add Windows, Linux/Xvfb with a compositor, and macOS Python/Qt jobs; keep native Swift and signature checks on macOS.
- [ ] Run updated instruction replays, the full local checks, and the public CI matrix. Fix platform-specific failures before claiming support.
- [ ] Review the complete branch, check publication content, fast-forward the public main branch, and publish the next release under DiyunZ.

## Local verification

- Python suite: 105 tests, 104 passed; one real Windows sharing test awaits Windows CI.
- Qt GUI: 22 real-window tests passed on macOS, including actual compositing and fractional render scales.
- A fresh isolated install created a private Qt environment using Python 3.14 without Qt, then the installed CLI opened and reused the HUD through the configured interpreter.
- Native Swift tests and signed installation passed locally. Cross-platform CI and final publication remain pending below.
