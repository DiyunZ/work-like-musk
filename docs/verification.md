# Verification scope

Implementation checks are reproducible through the commands in the README and the repository CI workflow.

| Area | Checks |
| --- | --- |
| Python state CLI | Task isolation, ordered transitions, reopen behavior, revision conflicts, skip confirmation, input validation, and runtime file protections. |
| macOS installer | Required skill identity, language selection, backups, rollback, file metadata, and unfinished transaction checks. |
| Native HUD | State decoding, task identity, placement, preferences, localization, stage readiness, and interaction behavior. |
| App build | Swift compilation with warnings treated as errors, and local ad-hoc signing. |

The public package renames the existing skill and runtime namespace. Its original coaching workflow was exercised with bounded scenario replays, including stage pauses, clarification handling, explicit continuous execution, and evidence-limited progress. Those observations are not a controlled benchmark and private conversations are not included here.

The tests do not establish a general productivity benefit. They do not prove future agent compliance or continued compatibility with changing Codex desktop internals. A displayed checkpoint reflects the agent's report; assess its stated evidence against the actual deliverable.

The initial public release is checked on Apple Silicon macOS. The build script also targets Intel when run on an Intel Mac, but this release has not been independently verified on Intel hardware. The core Markdown instructions have no native dependency; cross-host behavior has not been comprehensively evaluated.
