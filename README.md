<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

# Work Like Musk

**Five-step project coaching for AI agents.**

Work Like Musk uses **question requirements → delete → simplify → accelerate → automate** to guide project work. Before committing effort, the assistant examines its own proposal, explains one concrete recommendation, acts on it, and checks the result.

Coaching happens in the conversation. **By default, the assistant completes one stage and waits for your reply.** You can explicitly request continuous execution or practice making the judgments yourself.

## Why use it?

- **Identify unnecessary work early.** Question why a requirement exists before building around it.
- **Understand the judgment.** Each consequential recommendation connects a reason, an action, and a success signal.
- **Keep control of the pace.** The next stage waits until you ask to continue.
- **Keep the outcome reviewable.** Final replies retain the deliverable, evidence, unresolved limits, and next move.

## Install

The skill consists of Markdown instructions and optional Codex UI metadata. Using it requires a host that can load Agent Skills; project execution also needs the tools and authorization appropriate to that work.

The installer uses **Python 3.9+ and the standard library**:

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/install.py --agent claude-code
```

On Windows / PowerShell, use `python` instead of `python3`.

| `--agent` | Personal installation directory | Invocation |
| --- | --- | --- |
| `codex` | `.codex/skills/work-like-musk` | `$work-like-musk` |
| `claude-code` | `.claude/skills/work-like-musk` | `/work-like-musk` |
| `cursor` | `.cursor/skills/work-like-musk` | Ask to use `work-like-musk` |
| `gemini-cli` | `.gemini/skills/work-like-musk` | Ask to use `work-like-musk` |
| `opencode` | `.config/opencode/skills/work-like-musk` | Ask to use `work-like-musk` |
| `generic` | `.agents/skills/work-like-musk` | Use the host's supported skill invocation |

Restart your agent or reload Skills after installation. The default preset is Codex. OpenCode respects `XDG_CONFIG_HOME`. Use `--skill "<actual-skill-directory>"` for a custom or project-level location. See [compatibility and host references](docs/compatibility.md).

The same command upgrades an existing installation, preserving custom guidance, invocation policy, and supported file metadata. Changed files are backed up outside the skill directory; the command prints the backup path. An unfinished installation must be inspected before another upgrade can proceed.

**Upgrading from the HUD version:** the installer removes the old managed HUD instructions and backs up and removes its known app, scripts, guides, and configuration files. Custom files and project session data are preserved. Close an already-running old HUD. Shared environments outside the skill directory are left intact. Omit the former `--hud`, `--app`, and `--language` options; coaching follows your conversation language.

## Start a project

```text
$work-like-musk
Help me build a small tool that converts a CSV file into a weekly report.
Coach and complete one stage at a time, then wait for my reply.
```

Use your host's invocation from the table. The assistant first clarifies the real outcome and the acceptance condition for **Question requirements**. It can inspect the project and carry out authorized work within that stage. A clarification about the current result does not automatically start the next stage.

A stage closeout might look like this:

> **01 · Question requirements — complete**
>
> The required outcome is one local report from one CSV. A dashboard and scheduled service are implementation choices; assess whether they are needed before building them.
>
> **Evidence:** output, input format, and acceptance criteria are agreed; runtime behavior has not been tested.
>
> **Next:** examine what can be deleted. Stages 02–05 remain pending. Ask to continue with Delete when ready.

This is a fictional coaching example, not a Musk quotation or a real user conversation.

## Five steps, each grounded in evidence

| Step | Core question | Evidence to seek |
| --- | --- | --- |
| **01 Question requirements** | What problem does this requirement solve? | A clear outcome, source, constraints, and acceptance criteria. |
| **02 Delete** | Can this part disappear entirely? | A reversible trial supporting removal or retention. |
| **03 Simplify** | What is the smallest complete path to the outcome? | A usable end-to-end result and relevant checks. |
| **04 Accelerate** | Where does the time actually go? | An observed bottleneck and a relevant before/after comparison. |
| **05 Automate** | Is this operation worth automating? | A stable operation, worthwhile benefit, and verified failure handling. |

New evidence can reopen an earlier stage. A design checkpoint establishes design progress; operational claims need execution evidence. Stages outside the requested scope remain pending. The method guides decisions without inventing five changes for every task.

## Choose your pace

| You want… | Say… |
| --- | --- |
| A pause after each stage **(default)** | “Complete this stage, explain the evidence, then wait.” |
| Continuous execution | “Proceed between stages without waiting; retain each stage's conclusion and evidence.” |
| Personal reasoning practice | “Ask me one question at a time and let me reason it through.” |

Coaching follows the conversation language. `SKILL.md` itself is written in English.

## Repository and checks

```text
skills/work-like-musk/   Coaching instructions and agent metadata
scripts/install.py      Installer and migration from the former HUD version
tests/                  Installation, migration, and recovery checks
docs/                   Compatibility and verification scope
```

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The CI matrix covers Windows, Linux, macOS, and the minimum Python version without GUI dependencies. Implementation checks do not establish a general productivity benefit or guarantee future agent compliance. See [verification scope](docs/verification.md) and [contributing](CONTRIBUTING.md).

## Source and license

The five-step order comes from [Everyday Astronaut's summary of its 2021 Elon Musk interview](https://everydayastronaut.com/starbase-tour-and-interview-with-elon-musk/). The coaching loop, stage pauses, evidence rules, and agent integration are this project's adaptations.

This is an independent project with no affiliation with or endorsement by Elon Musk, his companies, or OpenAI. The [MIT license](LICENSE) applies to project material to the extent that rights exist; it grants no third-party name, likeness, or endorsement rights.
