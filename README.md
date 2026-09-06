<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

![Work Like Musk — five-step coaching for AI agents](docs/assets/work-like-musk-hero.png)

<p align="center"><strong>Give your AI agent a project coach, one decision at a time.</strong></p>
<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="skills/work-like-musk/SKILL.md"><img alt="Agent Skill" src="https://img.shields.io/badge/Agent-Skill-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="docs/hud.md"><img alt="Optional HUD: macOS 14+" src="https://img.shields.io/badge/Optional_HUD-macOS_14%2B-635BFF?style=flat-square&labelColor=171717"></a>
</p>

**Work Like Musk** coaches an AI agent through **question → delete → simplify → accelerate → automate**. Before committing effort, the agent challenges its own plan, explains a concrete recommendation, acts on it, and checks the result.

**The default is one stage, then your reply.** You can ask for continuous execution when you want it.

## Why use it?

- **Catch unnecessary work early.** Question the requirement before building around it.
- **Learn from the decisions.** Get a specific recommendation, the reason behind it, and the next check.
- **Keep control of the pace.** Finishing a stage leaves the next one pending until you continue.
- **See what completion means.** Final replies retain scope, evidence, unresolved limits, and the next move.

## Install

Install for Codex with the [Skills CLI](https://github.com/vercel-labs/skills):

```sh
npx skills add DiyunZ/work-like-musk --skill work-like-musk --agent codex --global --copy --yes
```

For another supported agent, omit `--agent codex --yes` and choose your agent when prompted. The core is a Markdown skill; the native HUD is optional and installed separately. This project is developed and checked with Codex. Behavior in other hosts depends on their skill support and instructions.

Prefer a manual install? Copy [`skills/work-like-musk`](skills/work-like-musk) into your agent's skill directory. For Codex, the default personal location is `~/.codex/skills/work-like-musk/`. Start a new task after installing so it can discover the skill.

## Try it

```text
$work-like-musk
Help me build a tool that turns a CSV file into a weekly report.
Coach one stage at a time and wait for my reply before the next.
```

The agent starts by establishing the actual outcome and the evidence needed to complete **Question**. It can inspect the project and do authorized work inside that stage. A clarification stays within the current stage.

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
| Coaching without the HUD | “Use the skill without the progress panel.” |

Ask in English or Chinese; the coaching follows your conversation language. The instructions in `SKILL.md` are English.

## Optional: a live macOS HUD

The companion app displays the agent's reported stages beside the current Codex task title, with a floating option and menu-bar fallback. It includes English and Simplified Chinese labels, per-task state, hover explanations, and appearance controls.

- A rotating ring indicates active work; a red breathing dot indicates a stage waiting for your prompt.
- Checkmarks follow the agent's evidence and stage closeout. The panel does not verify the project independently.
- Local files and a native app are sufficient. The HUD code has no network service or API-key requirement.

Requires **macOS 14+, Python 3.9+, and Apple Swift command-line tools**. After installing the skill:

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/build.py
python3 scripts/install.py --language en
```

Use `--language zh-CN` for Chinese HUD labels. The installer targets the default Codex personal skill directory; use `--skill` for a different location. It backs up replaced files. The app is built and ad-hoc signed locally; this is not a notarized binary distribution.

See [HUD setup, permissions, and troubleshooting](docs/hud.md) for title tracking and recovery details. The Codex adapter depends on local desktop task metadata and may need updates when Codex changes.

## What is included?

```text
skills/work-like-musk/   The installable skill, protocol guide, and state CLI
native/                 Optional SwiftUI/AppKit HUD
scripts/                Build, HUD installer, preview, and native test runner
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
