# Cross-platform integrated HUD

## Outcome

Work Like Musk installs its coaching skill and a working HUD on Windows, Linux desktops, and macOS. It supports local Codex, Claude Code, Cursor, Gemini CLI, OpenCode, and other hosts that can load Agent Skills and run local Python commands. The HUD remains part of the product.

The selected cross-platform experience is a standalone floating progress strip that explicitly names its bound task. The existing macOS/Codex title-following HUD remains available and is the default for that environment.

The portable progress strip must follow the current macOS HUD's visual design: a compact 248-by-30 core, persistent stage symbols, small completion/waiting/blocked badges, matching colors and timing, and a single eligible connector animation. A concise task binding accompanies that core in its standalone window. Native UI source is the visual reference; do not redesign the portable version as a dashboard or redistribute Apple symbol artwork.

The progress core has true alpha transparency and antialiased vector drawing at normal, fractional, and Retina/high-DPI scales. Linux must have a compositor. The task label may use a compact translucent backing; do not fill the entire progress strip.

## Architecture

- Keep the existing five-stage state schema, ordered transitions, revision checks, confirmed skips, and reopen semantics.
- Use a small shared Python runtime module for operating-system file locks. Windows uses `msvcrt`; POSIX uses `fcntl`. Both installer and reporter hold real OS locks and release them on exit.
- Add a Qt floating HUD using PySide6 Essentials, with a translucent frameless window and vector QPainter rendering. It reads one explicitly bound project/task state, renders the five existing stage identities, exposes reasons, and clears progress if the state becomes invalid. A title, project name, and short task identifier distinguish concurrently open tasks.
- Keep the Swift HUD for Codex on macOS 14+. Backend selection changes the display implementation, never whether the HUD is included.
- The installer selects an agent's skill location, preserves the existing language configuration, and stores its chosen agent/backend separately from the native language file. It checks the GUI runtime before publishing a portable installation.
- Portable installs reuse a compatible Qt interpreter or prepare an isolated runtime after installation ownership checks. `assets/portable-runtime.json` records its absolute interpreter path, keeping the state CLI independent of GUI dependencies. Preserve that file in the existing backup/rollback transaction.

## Interfaces

`runtime_support.file_lock(stream, blocking=True)` is a context manager for an already-open lock file. Nonblocking contention raises an error; a failed acquisition never releases another owner's lock.

`five_step.py setup --new-task` creates a fresh, opaque `wlm-<uuid>` identifier when the host supplies none. It returns `taskId` alongside the existing result fields. Every later command uses that returned `--task` value. `--new-task` is explicit and mutually exclusive with `--task`; it overrides a Codex environment identifier. Setup without either retains the existing Codex environment behavior and fails if identity is unavailable.

`setup` and `open` accept `--hud native|portable` as an explicit display override. The saved backend otherwise decides. An old installation without backend metadata uses its native app on macOS when present; otherwise it uses the bundled portable HUD. Explicitly selected native startup never silently changes backends after failure.

The portable process receives `--project`, `--task`, `--state`, `--language`, and an internal `--ready-file` path. It validates the state against the supplied identity, acquires a per-task HUD lock, creates the window, and then writes an `opened` response. A second process for that task returns `already_open`. Startup errors are returned through the same bounded handshake; state is retained. The parent does not report success merely because a process was spawned.

`scripts/install.py --agent codex|claude-code|cursor|gemini-cli|opencode|generic --hud auto|native|portable --language en|zh-CN` installs the complete product. `--skill` remains the override for an exact location. `--app` remains an explicit prebuilt native app input. The default agent remains Codex for existing callers.

## Task identity and visible behavior

- Prefer an actual host-provided session ID, passed explicitly outside Codex. Do not infer IDs from titles or another task's most recent file.
- When no host ID is available, generate a local tracking ID with `--new-task` and retain it in that conversation. This ID is a HUD binding, not a claim about the host's internal identity.
- Portable windows remain bound to their named tasks. They do not claim to follow another agent's active tab automatically.
- All newly created stages are pending. Only the next eligible stage waits; active or blocked work suppresses later readiness. Completing a stage never starts the next.
- Default coaching still completes one stage and waits for the user's reply. The final response retains the checkpoint and next action.

## Installation and recovery

Python 3.9+ is required. Portable GUI startup requires Qt for Python 6.8+ and a graphical desktop. Native Codex mode requires macOS 14+ and Swift command-line tools. Missing dependencies and headless sessions produce concrete setup errors instead of a partial-success claim.

Preserve unrelated files, existing custom instructions, agent metadata, symlinks, and the metadata supported by each operating system. Preserve the macOS `ditto` path for its extended-attribute guarantees. Use standard copy operations on Windows and Linux. Keep transaction backups, entrypoint-last publication, rollback, and unfinished-transaction checks.

## Verification

1. Run the existing state and installer regressions, plus explicit-ID creation, concurrent locks, backend routing, startup failures, and portable installation tests.
2. Exercise the actual Qt window with controlled English and Chinese states, two independent tasks, corrupt state, and a completed first stage with later stages pending.
   Check transparent pixels, antialiased edges, render output at 1×/1.25×/1.5×/1.75×/2×, and actual window composition over a synthetic background.
3. Run Python and portable GUI checks on Windows, Linux under Xvfb with a compositor, and macOS. Keep native Swift and signed-install checks on macOS.
4. Replay skill startup for Windows/Claude Code, Linux/Gemini CLI, and macOS/Cursor. Baseline instructions reject all three; updated instructions must use the selected floating HUD without fabricating host IDs or skipping stages.
5. State the evidence boundary: runtime and installation compatibility do not prove every third-party agent's future behavior. Record which hosts were checked against their documented skill interfaces and which live application integrations were directly observed.

## Sources for host discovery

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Cursor skills](https://cursor.com/docs/skills)
- [Gemini CLI skills](https://geminicli.com/docs/cli/skills/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
- [Qt translucent windows](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#creating-translucent-windows)
- [Qt high-DPI drawing](https://doc.qt.io/qt-6/highdpi.html)
- [Python Windows locking](https://docs.python.org/3/library/msvcrt.html)
