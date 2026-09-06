<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

![Work Like Musk — five-step coaching for AI agents](docs/assets/work-like-musk-hero.png)

<p align="center"><strong>Give your Codex agent a project coach and a live progress strip.</strong></p>
<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="skills/work-like-musk/SKILL.md"><img alt="Agent Skill" src="https://img.shields.io/badge/Agent-Skill-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="docs/hud.md"><img alt="Integrated HUD: macOS 14+" src="https://img.shields.io/badge/Integrated_HUD-macOS_14%2B-635BFF?style=flat-square&labelColor=171717"></a>
</p>

**Work Like Musk** combines a Codex project coach and an integrated native progress HUD. It guides the agent through **question → delete → simplify → accelerate → automate**. Before committing effort, the agent challenges its own plan, explains a concrete recommendation, acts on it, and checks the result.

**The default is one stage, then your reply.** You can ask for continuous execution when you want it.

## Why use it?

- **Catch unnecessary work early.** Question the requirement before building around it.
- **Learn from the decisions.** Get a specific recommendation, the reason behind it, and the next check.
- **Keep control of the pace.** Finishing a stage leaves the next one pending until you continue.
- **Follow progress beside your task title.** The built-in HUD shows the current stage; final replies retain scope, evidence, unresolved limits, and the next move.

## Install

The complete product supports **local Codex on macOS 14+**, with **Python 3.9+** and **Apple Swift command-line tools**. One installer builds and installs the coaching skill, state helper, and native HUD together:

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/install.py --language en
```

Use `--language zh-CN` for Chinese HUD labels. The default destination is `~/.codex/skills/work-like-musk/`. Start a new Codex task after installing and invoke `$work-like-musk`; it initializes the task's progress and opens the HUD. On first use, enable title tracking in HUD Settings and grant the app macOS Accessibility permission.

The same command updates an existing installation and backs up replaced files. If you installed only the Markdown skill previously, run this installer to complete the product. Use `--skill /absolute/skill/directory` for a custom location. A missing HUD is an incomplete setup that the agent must surface and repair.

## Try it

```text
$work-like-musk
Help me build a tool that turns a CSV file into a weekly report.
Coach one stage at a time and wait for my reply before the next.
```

The agent checks the installation, starts the task's HUD, and establishes the actual outcome and the evidence needed to complete **Question**. It can inspect the project and do authorized work inside that stage. A clarification stays within the current stage.

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

## Progress that lives beside your task

The integrated HUD displays the agent's reported stages beside the current Codex task title, with a floating option and menu-bar fallback. It includes English and Simplified Chinese labels, per-task state, hover explanations, and appearance controls.

- A rotating ring indicates active work; a red breathing dot indicates a stage waiting for your prompt.
- Checkmarks follow the agent's evidence and stage closeout. The panel does not verify the project independently.
- Local files and a native app are sufficient. The HUD code has no network service or API-key requirement.

The HUD is installed with the skill and starts with each activated project session. Its native process keeps display state local while the agent provides coaching and reports progress. The app is built and ad-hoc signed locally; this is not a notarized binary distribution.

See [HUD setup, permissions, and troubleshooting](docs/hud.md) for title tracking and recovery details. The Codex adapter depends on local desktop task metadata and may need updates when Codex changes.

## What is included?

```text
skills/work-like-musk/   Coaching instructions, protocol guide, and state CLI
native/                 Integrated SwiftUI/AppKit progress HUD
scripts/                Unified product installer, build, preview, and test runner
tests/                  State, installer, and native regression checks
docs/                   HUD guide and original English artwork
```

To run the implementation checks on macOS:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/test_native.py
python3 scripts/build.py
```

These checks cover implementation behavior. They do not establish a general productivity improvement or guarantee that an agent will always follow the skill. See [verification scope](docs/verification.md) and [contributing](CONTRIBUTING.md).

## Inspiration and license

The sequence comes from [Everyday Astronaut's 2021 summary of its interview with Elon Musk](https://everydayastronaut.com/starbase-tour-and-interview-with-elon-musk/). The coaching loop, stage checkpoints, evidence rules, and agent integration are this project's adaptations.

Independent project; not affiliated with or endorsed by Elon Musk, his companies, or OpenAI. The [MIT license](LICENSE) covers project material to the extent rights exist; it grants no endorsement or rights to third-party names or likenesses. The hero is [original AI-generated editorial artwork](docs/assets/artwork.md). README presentation takes inspiration from [Archify](https://github.com/tt-a1i/archify)'s clear visual introduction and language switch; its assets and copy are not reused.
