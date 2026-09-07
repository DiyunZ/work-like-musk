<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

![Work Like Musk — five-step coaching for AI agents](docs/assets/work-like-musk-hero.png)

<p align="center"><strong>Give your AI agent a project coach and a live progress strip.</strong></p>
<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="skills/work-like-musk/SKILL.md"><img alt="Agent Skill" src="https://img.shields.io/badge/Agent-Skill-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="docs/hud.md"><img alt="Windows · Linux · macOS" src="https://img.shields.io/badge/HUD-Windows_%7C_Linux_%7C_macOS-635BFF?style=flat-square&labelColor=171717"></a>
</p>

**Work Like Musk** combines an AI project coach and an integrated progress HUD across Windows, Linux desktops, and macOS. It guides the agent through **question → delete → simplify → accelerate → automate**. Before committing effort, the agent challenges its own plan, explains a concrete recommendation, acts on it, and checks the result.

**The default is one stage, then your reply.** You can ask for continuous execution when you want it.

## Why use it?

- **Catch unnecessary work early.** Question the requirement before building around it.
- **Learn from the decisions.** Get a specific recommendation, the reason behind it, and the next check.
- **Keep control of the pace.** Finishing a stage leaves the next one pending until you continue.
- **See which task the progress belongs to.** The built-in HUD shows the current stage; final replies retain scope, evidence, unresolved limits, and the next move.

## Install

Requires **Python 3.9+** and a graphical desktop for the floating HUD. Local agents must be able to load Agent Skills and run commands. The installer includes the coaching skill, progress tools, and HUD, and prepares its Qt runtime automatically. The first portable install needs internet access if Qt is not already available.

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/install.py --agent claude-code --language en
```

On **Windows / PowerShell**, use:

```powershell
python scripts/install.py --agent claude-code --language en
```

Choose your agent; each preset uses its documented personal skill directory:

| `--agent` | Destination under your home directory | How to start |
| --- | --- | --- |
| `codex` | `.codex/skills/work-like-musk` | `$work-like-musk` |
| `claude-code` | `.claude/skills/work-like-musk` | `/work-like-musk` |
| `cursor` | `.cursor/skills/work-like-musk` | Ask to use `work-like-musk` |
| `gemini-cli` | `.gemini/skills/work-like-musk` | Ask to use `work-like-musk` |
| `opencode` | `.config/opencode/skills/work-like-musk` | Ask to use `work-like-musk` |
| `generic` | `.agents/skills/work-like-musk` | Use your host's skill loader |

Restart or reload skills in your agent after installation. OpenCode respects `XDG_CONFIG_HOME`. For a custom or project-level directory, add `--skill "<actual-skill-directory>"`. Other agents need compatible Agent Skills discovery and local command execution; `generic` does not add capabilities to a host that lacks them. See [compatibility and primary host references](docs/compatibility.md).

Use `--language zh-CN` for Chinese HUD labels and report guidance. If no agent is specified, the default is Codex. On **macOS 14+ with Codex desktop**, the installer builds the existing native title-following HUD and requires Apple Swift command-line tools; this backend does not need Qt. Use `--hud portable` for Codex CLI or to choose the floating window on macOS.

The same command updates an installation, preserves its language/backend choice and customized instructions, and backs up replaced files. Restart the HUD after upgrading so it loads the updated code. A missing HUD is an incomplete setup to repair. See [HUD setup and troubleshooting](docs/hud.md).

## Try it

```text
$work-like-musk
Help me build a tool that turns a CSV file into a weekly report.
Coach one stage at a time and wait for my reply before the next.
```

In other agents, invoke the skill as shown in the table or ask “Use work-like-musk.” The agent checks the installation, starts the task's HUD, and establishes the actual outcome and the evidence needed to complete **Question**. It can inspect the project and do authorized work inside that stage. A clarification stays within the current stage.

An illustrative checkpoint might look like this:

> **01 · Question — complete**
>
> The required result is one local report from one CSV. A dashboard and scheduled service are implementation choices, so let's test whether they have a job before building them.
>
> **Evidence:** the required output, input format, and acceptance check are agreed. No runtime behavior is verified yet.
>
> **Next:** examine what can be deleted. Steps 02–05 remain pending. Reply “continue to Delete” to begin.

This is a fictional example of the intended coaching style, not a quote from Musk or a recorded user conversation.

## Five steps, with a reason to move on

| Step | The question | Evidence to look for |
| --- | --- | --- |
| **01 Question** | What problem does this requirement solve? | A clear outcome, source, constraints, and acceptance check. |
| **02 Delete** | Can this part disappear? | A reversible trial showing removal works, or a reason to retain it. |
| **03 Simplify** | What is the smallest complete path? | A useful end-to-end result with the necessary checks. |
| **04 Accelerate** | Where does time actually go? | An observed bottleneck and a relevant before/after comparison. |
| **05 Automate** | Is this worth repeating automatically? | A stable operation, a worthwhile benefit, and tested failure handling. |

The skill revisits earlier steps when evidence changes. A design checkmark describes design progress; runtime claims need runtime evidence. Stages outside your requested scope stay pending. The five steps are decision tools, not a requirement to invent five changes.

## Choose your pace

| You want… | Say… |
| --- | --- |
| Stage checkpoints **(default)** | “Finish this stage, show the evidence, then wait.” |
| Continuous execution | “Work through the stages without waiting; retain each checkpoint in the final reply.” |
| Hands-on practice | “Ask me one question at a time and let me do the reasoning.” |

Ask in English or Chinese; the coaching follows your conversation language. The instructions in `SKILL.md` are English.

## Progress that names its task

The portable HUD is a movable floating strip with the **task title, project, and task identifier**. It stays bound to that task when you switch apps or conversations; different tasks can have separate windows. Agents without a host session ID get a unique local tracking ID and retain it in the current conversation.

The progress core follows the native Mac design: the same compact layout, colors, state badges, and animation timing, on a truly transparent background. Vector drawing stays sharp on high-DPI screens and fractional scaling. Linux needs a compositing desktop; see [compatibility](docs/compatibility.md).

- A rotating ring indicates active work; a red breathing indicator marks the next stage waiting for your prompt.
- Hover for the reported reason and time. The menu controls Always on top and Reduce motion.
- Checkmarks reflect the agent's stated evidence. The panel does not verify the project independently.
- Local files and the GUI runtime are sufficient; the HUD has no network service or API-key requirement.

The native macOS/Codex backend additionally supports verified title following, menu-bar placement, and appearance controls. Enable title tracking and grant macOS Accessibility permission in HUD Settings. It depends on local Codex task metadata and may need updates when Codex changes. The app is built and ad-hoc signed locally.

The HUD is included in every activated project session. Headless terminals, SSH sessions without a display, and cloud-only agents cannot show the complete product locally.

## What is included?

```text
skills/work-like-musk/   Coaching instructions, protocol, state CLI, and portable HUD
native/                 macOS/Codex SwiftUI/AppKit HUD
scripts/                Unified product installer, build, preview, and test runner
tests/                  State, installer, portable GUI, and native regression checks
docs/                   HUD guide and original English artwork
```

Run the Python checks with Qt and an active desktop (`python` on Windows):

```sh
python3 -m pip install 'PySide6-Essentials>=6.8,<7'
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Linux CI uses Xvfb with a compositor; [CONTRIBUTING](CONTRIBUTING.md) has the local command. The native macOS backend also runs `python3 scripts/test_native.py` and `python3 scripts/build.py`. CI exercises Windows, Linux, macOS, and the minimum Python version.

These checks cover implementation behavior. They do not establish a general productivity improvement or guarantee that an agent will always follow the skill. See [verification scope](docs/verification.md) and [contributing](CONTRIBUTING.md).

## Inspiration and license

The sequence comes from [Everyday Astronaut's 2021 summary of its interview with Elon Musk](https://everydayastronaut.com/starbase-tour-and-interview-with-elon-musk/). The coaching loop, stage checkpoints, evidence rules, and agent integration are this project's adaptations.

Independent project; not affiliated with or endorsed by Elon Musk, his companies, or OpenAI. The [MIT license](LICENSE) covers project material to the extent rights exist; it grants no endorsement or rights to third-party names or likenesses.

The portable HUD uses Qt for Python, installed separately from its official package. Its licenses and source are listed in [third-party notices](THIRD_PARTY_NOTICES.md).
