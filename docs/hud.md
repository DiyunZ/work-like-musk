# Integrated live HUD

[English](hud.md) · [简体中文](hud.zh-CN.md) · [README](../README.md)

The HUD is a built-in part of Work Like Musk on Windows, Linux desktops, and macOS. It renders stage events reported by the coach and is installed with the skill.

## Install the complete product

Clone the repository, then select your agent:

```sh
python3 scripts/install.py --agent claude-code --language en
```

Use `python` on Windows. The [README agent table](../README.md#install) lists all presets and their directories. A portable installation requires Python 3.9+ and a graphical desktop. The installer reuses a suitable Qt for Python installation or downloads it into a private Python environment under `~/.work-like-musk/runtimes/`. It records the GUI interpreter so the agent's Python needs no Qt packages. Native Codex desktop on macOS 14+ requires Swift command-line tools to build its app. Choose `--hud portable` for Codex CLI or for an explicitly bound floating window on macOS.

Use `--language zh-CN` for Chinese labels and report guidance. A terminal install without a language option asks you to choose; a first non-interactive install requires it. Upgrades preserve the saved language and display backend unless explicitly changed. Use `--skill "<actual-skill-directory>"` for a custom destination.

The installer includes coaching instructions, state and locking helpers, both protocol guides, configuration, and the selected HUD. It preserves customized instructions and existing agent metadata. Replaced files are backed up under `~/.codex/skill-backups/work-like-musk-hud/` for Codex or `~/.work-like-musk/skill-backups/` for other agents. It prints the exact backup path and transaction status. Inspect unfinished transactions before retrying; preserve their recovery files. Restart the HUD after upgrading to load its updated code.

## Portable floating window

Invoke the skill through your agent. It opens a separate window showing the **task title, project name, and shortened task ID**. The window remains bound to that task as you switch applications or conversations. Two tasks have independent windows; opening the same task again reuses its existing window.

The 248-by-30 progress core follows the native Mac geometry, state colors, and motion. Its background is transparent; the task label has a small translucent backing for readability. Qt paints vector shapes in logical display units with antialiasing, including at 125%, 150%, 175%, and 200% scaling. Text still uses the operating system's fonts. Linux transparency requires Wayland or an X11 desktop with a compositor. See [Qt's transparency requirements](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#creating-translucent-windows) and [high-DPI drawing](https://doc.qt.io/qt-6/highdpi.html).

Drag the strip to move it. Use the three-dot menu or right-click to toggle Always on top and Reduce motion. Close or Escape dismisses the window while keeping its state. The portable HUD reads only the supplied task's progress files; it does not inspect the foreground app, agent chat, or another task's index. No Accessibility permission is required for this mode.

If your agent has no session ID, the tool generates one local tracking ID on first setup. The agent retains that ID in the current conversation and passes it explicitly on subsequent commands. An ID returned with a startup error must also be retained for the retry. The [protocol guide](../skills/work-like-musk/references/live-progress.md) documents the exact commands.

## Native Codex title tracking (macOS 14+)

For the native backend, invoke `$work-like-musk` for a Codex desktop project. The agent checks the installation, sets up that task's session, and opens the HUD as part of the standard workflow. In the HUD's settings, choose **Enable Title Tracking…**, allow the HUD in **System Settings → Privacy & Security → Accessibility**, and return to Codex.

The app reads the focused task header and toolbar geometry. It resolves an exact, unique title against local Codex task identity metadata using a read-only database query. It does not read chat messages, capture screenshots, or modify Codex controls. No network service, login item, or daemon is installed by this project. Your AI host has its own data handling, separate from the HUD.

The adapter depends on Codex's local task index and visible header structure. This title-following adapter does not cover other hosts, cloud tasks, duplicate titles, or future Codex changes. Other local agents use the portable backend. Missing permission or uncertain task identity hides progress. If a verified task has too little title-bar space, the app can use the menu bar. Settings shows the last verified task and tracking status.

## Reading the indicators

| Indicator | Meaning |
| --- | --- |
| Rotating ring | The agent has reported active stage work. |
| Red breathing indicator | The next eligible stage is waiting for your prompt. |
| Checkmark | The agent has reported completion and its evidence. |
| Amber indicator | A required input or external condition is blocking work. |

Hover over a symbol for its stage, status, report reason, and report time. The window identifies the task. Hovering or clicking does not start work. Reduced Motion uses static indicators. Native Settings additionally controls placement, theme, colors, scale, and contrast-related appearance.

The final coaching reply remains the human-readable record of scope and evidence. A visual checkmark is not an independent acceptance test.

## State and privacy

Sessions are stored under `<project>/.work-like-musk/sessions/`, with one file per task identity. State contains project paths, task IDs, titles, reasons, and timestamps. Treat it as local project data and exclude it from public commits. Add `.work-like-musk/` to your project's ignore file when using the HUD.

The CLI defaults to the actual `CODEX_THREAD_ID`. In another environment, provide its actual session ID through `--task`, or use `setup --new-task` once and retain its returned local tracking ID. Reuse that ID in the current conversation; do not choose a session by recency. Read the current revision before a report; stale revisions are rejected. Reopening a stage clears dependent later states. Skipping unfinished stages requires the ordering reminder followed by a separate user confirmation.

The [agent protocol guide](../skills/work-like-musk/references/live-progress.md) describes the commands and boundaries. Do not edit session JSON by hand to force a desired display.

## Troubleshooting

- **Qt download or environment creation failed:** rerun the installer after fixing the reported network, package, or Python `venv` error. It installs `PySide6-Essentials>=6.8,<7` in its private runtime when needed. Python, OS, and CPU must have a compatible [official wheel](https://pypi.org/project/PySide6-Essentials/). A missing runtime does not reset stage progress.
- **Qt platform plugin or transparency unavailable:** use a local graphical session. On Linux, enable the desktop's compositor; bare X11 without one cannot provide the required alpha transparency. The launcher reports this as an incomplete setup. Missing system libraries are listed in the Qt/platform error and the [Linux Qt requirements](https://doc.qt.io/qt-6/linux-requirements.html).
- **No graphical display:** run the agent and Python in a local desktop session with a working display. Headless SSH or a cloud-only agent cannot show the full product; installation alone does not establish visible startup.
- **Portable window closed:** ask the agent to reopen the same task with its retained `taskId`. Progress is preserved.
- **Native panel missing:** return to the registered Codex task, check Accessibility permission and HUD Settings status, and ensure the title is unique.
- **Native permission appears enabled after a rebuild:** macOS may retain the old locally signed app identity. Remove the outdated entry and add the installed `assets/FiveStepHUD.app` again.
- **Instructions exist but HUD files are missing:** rerun the unified installer for the same agent and skill directory, then reopen this task. A failed setup retains existing progress and reports its task identity.
- **Revision is stale:** read the latest state and reassess the event before retrying.
- **Linked or malformed runtime files:** preserve them and inspect their origin. The CLI rejects them rather than replacing them.

For an isolated native visual preview on macOS, run `python3 scripts/preview.py --language en`. This uses synthetic state and never inspects another app. Its buttons exercise the display; they are not an alternative way to complete real project work.
