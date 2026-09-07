# Compatibility

The complete product includes the coaching skill, state runtime, and a visible HUD. A local host needs Agent Skills support, command execution, Python 3.9+, and access to the project files.

| Environment | Default HUD | Additional requirement |
| --- | --- | --- |
| Windows desktop | Portable floating window | Compatible Qt for Python wheel; installed automatically |
| Linux desktop | Portable floating window | Qt for Python and a compositing desktop (Wayland or X11 with a compositor) |
| macOS with Claude Code, Cursor, Gemini CLI, OpenCode, or a generic host | Portable floating window | Compatible Qt for Python wheel; installed automatically |
| macOS 14+ with Codex desktop | Native title-following HUD | Apple Swift command-line tools to build; Accessibility permission for tracking |
| Codex CLI on any supported desktop | Choose `--hud portable` | Qt for Python and a compositing desktop |

The installer uses `PySide6-Essentials>=6.8,<7` and selects an official wheel compatible with Python, OS, and CPU. For example, [6.8.3 supports Python 3.9](https://pypi.org/project/PySide6-Essentials/6.8.3/) and includes macOS 12+ universal and Linux x86-64 glibc 2.28+ wheels; newer releases can have higher minimums. This is not support for every historical OS release or CPU. When needed, the installer creates a private runtime without changing system Python packages.

Portable windows explicitly show their bound task. They do not automatically follow another agent's active conversation. The CLI uses an actual host-provided session ID, or creates one local tracking ID with `setup --new-task` for the agent to retain in that conversation. Native tracking requires the real Codex task ID.

## Agent discovery

The installer presets follow the hosts' documented personal skill directories. Host versions and policies can change; a directory contract is distinct from an end-to-end run inside each agent application.

| Preset | Host documentation |
| --- | --- |
| `codex` | [Codex Agent Skills](https://developers.openai.com/codex/skills/) |
| `claude-code` | [Claude Code Skills](https://code.claude.com/docs/en/skills) |
| `cursor` | [Cursor Agent Skills](https://cursor.com/docs/skills) |
| `gemini-cli` | [Gemini CLI Skills](https://geminicli.com/docs/cli/skills/) |
| `opencode` | [OpenCode Skills](https://opencode.ai/docs/skills/) |
| `generic` | A host that discovers `.agents/skills`, or a custom directory supplied with `--skill` |

Codex-specific `agents/openai.yaml` is supplemental metadata; the shared skill uses standard `name` and `description` frontmatter and Markdown instructions. Other agents do not need Codex tools, task databases, or environment variables for portable operation. Use each host's supported skill invocation or ask it to use `work-like-musk`.

## Limits and verification

The Python/Qt implementation is exercised by the Windows, Linux/Xvfb with xcompmgr, and macOS CI jobs; native Swift checks stay on macOS. The Python 3.9 floor is tested separately on Linux. See [verification scope](verification.md) for what the tests actually establish.

The named agents' discovery contracts and bounded instruction replays are checked separately from the runtime. This does not claim that every version of every agent application has been operated end to end. Cloud-only agents and headless environments cannot display the complete HUD product without an accessible graphical desktop. Linux CI uses Xvfb for GUI tests; that is not a visible user desktop.

The portable core uses genuine alpha transparency and vector drawing with Qt's [high-DPI support](https://doc.qt.io/qt-6/highdpi.html). Linux startup requires a compositor instead of falling back to an opaque window. The native geometry, colors, badges, and animation timing are shared visual targets; system font rendering can differ. See the [HUD troubleshooting guide](hud.md).
