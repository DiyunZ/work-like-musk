# Optional live HUD

[English](hud.md) · [简体中文](hud.zh-CN.md) · [README](../README.md)

The HUD is a standalone macOS companion for local Codex tasks. It renders stage events reported by the agent. Coaching works without it.

## Build and install

Install the core skill first, then clone the repository and run:

```sh
python3 scripts/build.py
python3 scripts/install.py --language en
```

Requires macOS 14+, Python 3.9+, and Apple Swift command-line tools. The build targets the current machine's architecture and signs the app locally. Use `--language zh-CN` for Chinese labels. A terminal install without the language option asks you to choose; a first non-interactive install requires the option.

The installer defaults to `~/.codex/skills/work-like-musk/`. It adds the application, state CLI, selected-language protocol guide, language configuration, and a managed HUD section. It preserves the rest of `SKILL.md` and the agent metadata. Use `--skill /absolute/skill/directory` for another install location.

Replaced files are backed up under `~/.codex/skill-backups/work-like-musk-hud/`. The installer prints the exact backup path and records its transaction status. An unfinished installation must be inspected before retrying; do not delete its backup to silence the check.

## Enable title tracking

Invoke `$work-like-musk` for a project. When available, the agent sets up that task's session and opens the app. In the HUD's settings, choose **Enable Title Tracking…**, allow the HUD in **System Settings → Privacy & Security → Accessibility**, and return to Codex.

The app reads the focused task header and toolbar geometry. It resolves an exact, unique title against local Codex task identity metadata using a read-only database query. It does not read chat messages, capture screenshots, or modify Codex controls. No network service, login item, or daemon is installed by this project. Your AI host has its own data handling, separate from the HUD.

The adapter depends on Codex's local task index and visible header structure. Other hosts, cloud tasks, duplicate titles, and future Codex changes are not covered. Missing permission or uncertain task identity hides progress. If a verified task has too little title-bar space, the app can use the menu bar. Settings shows the last verified task and tracking status.

## Reading the indicators

| Indicator | Meaning |
| --- | --- |
| Rotating ring | The agent has reported active stage work. |
| Red breathing dot | The next eligible stage is waiting for your prompt. |
| Checkmark | The agent has reported completion and its evidence. |
| Amber exclamation mark | A required input or external condition is blocking work. |

Hover over a symbol for the stage, status, report reason, task title, and report time. Hovering or clicking does not start work. Reduced Motion uses static indicators. Settings controls placement, theme, colors, scale, and contrast-related appearance.

The final coaching reply remains the human-readable record of scope and evidence. A visual checkmark is not an independent acceptance test.

## State and privacy

Sessions are stored under `<project>/.work-like-musk/sessions/`, with one file per task identity. State contains project paths, task IDs, titles, reasons, and timestamps. Treat it as local project data and exclude it from public commits. Add `.work-like-musk/` to your project's ignore file when using the HUD.

The CLI defaults to the actual `CODEX_THREAD_ID`. In another environment, provide the real task ID through `--task`. Read the current revision before a report; stale revisions are rejected. Reopening a stage clears dependent later states. Skipping unfinished stages requires the ordering reminder followed by a separate user confirmation.

The [agent protocol guide](../skills/work-like-musk/references/live-progress.md) describes the commands and boundaries. Do not edit session JSON by hand to force a desired display.

## Troubleshooting

- **No panel:** return to the registered Codex task, check Accessibility permission and the status in HUD settings, and ensure the task title is unique.
- **Permission appears enabled after a rebuild:** macOS may retain the previous locally signed app identity. Remove the outdated HUD entry and add the installed `assets/FiveStepHUD.app` again.
- **State exists but the app is missing:** build and install the HUD, then reopen the session. Setup preserves existing progress.
- **CLI says a revision is stale:** read the latest state and reassess the event before reporting it again.
- **Linked or malformed runtime files:** preserve them and inspect their origin. The CLI rejects them rather than replacing them.

For an isolated visual preview, run `python3 scripts/preview.py --language en`. This uses synthetic state and never inspects another app. Its buttons exercise the display; they are not an alternative way to complete real project work.
