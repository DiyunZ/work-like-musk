# Verification scope

The current product is a conversation-based coaching skill. Its installer and tests use the Python standard library. No GUI runtime is required for these checks.

## Installation and migration

Local macOS checks after HUD removal ran 24 tests: 23 passed and the Windows-specific reader-sharing test was skipped.

| Area | Observed checks |
| --- | --- |
| Fresh installation | A real installer subprocess with `python -S` installs only `SKILL.md` and `agents/openai.yaml`, without site packages or a GUI. All six agent directory presets are exercised. |
| Upgrade | Known legacy HUD files and managed instructions are removed after backup. Custom guidance, invocation policy, task data, CRLF content, symlinks, file modes, and macOS extended attributes are preserved in the covered cases. |
| Legacy name | An existing `musk-five-step` installation retains its name and matching invocation while its HUD is removed. |
| Recovery and ownership | Injected removal and publication failures restore previous files. Real competing processes contend on one installation lock. Forced exit and unfinished manifests prevent another installer from taking over the transaction. |
| Manifest writes | Temporary Windows sharing errors are retried within a bound; unrelated and persistent errors remain failures. Actual Windows reader sharing is exercised only on Windows. |

A separate local migration check used the previous Git revision's complete skill package, both legacy runtime configurations, and a fixture native app. The new installer ran with `python -S`; only the two skill files remained, and the original instructions and app were present in the backup. This checks migration, not operation of the retired app.

The skill frontmatter also passed `quick_validate.py`. That is structural validation, not evidence of coaching quality.

The [CI workflow](../.github/workflows/checks.yml) retains Windows, Linux, macOS, and the Python 3.9 floor. Qt setup, virtual displays, native builds, and GUI jobs have been removed. The changed CI workflow has not been run remotely as part of this local change.

## Coaching instruction review

The removal preserves the five-step order, one-stage-then-wait default, explicit continuous execution, personal practice, scope boundaries, and completion-evidence requirements. The following scenarios were reviewed against the instructions:

| Scenario | Before removal | Current instructions |
| --- | --- | --- |
| Start a CSV-to-weekly-report project | Initialize a task-specific HUD before the requirements checkpoint. | Establish the outcome and requirements checkpoint directly in the conversation. |
| Ask why a dashboard was considered unnecessary | Clarify the current judgment without advancing stages; maintain HUD state. | Clarify the same judgment without advancing stages; retain the useful explanation in the reply. |
| Explicitly request continuous work | Proceed across supported checkpoints and report HUD events. | Proceed across supported checkpoints and retain their conclusions and evidence in the final reply. |
| Finish a design proposal | Distinguish design completion from execution evidence in the reply and HUD report. | Preserve that distinction in the reply. |

This is an instruction-level review, not an independent live-agent replay or a controlled user study. Installation checks do not establish a productivity improvement, future compliance with the skill, or successful operation inside every named host/version. Whether removing the HUD reduces user effort remains a question for real project use.
