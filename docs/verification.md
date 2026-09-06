# Verification scope

Implementation checks are reproducible through the commands in the README and the repository CI workflow.

| Area | Checks |
| --- | --- |
| Python state CLI | Task isolation, ordered transitions, reopen behavior, revision conflicts, skip confirmation, input validation, and runtime file protections. |
| macOS installer | Complete fresh installation, automatic app build, unsupported-host rejection, language selection, backup/rollback, preserved customizations, and unfinished transaction checks. |
| Native HUD | State decoding, task identity, placement, preferences, localization, stage readiness, and interaction behavior. |
| App build | Swift compilation with warnings treated as errors, and local ad-hoc signing. |

The public package renames the existing skill and runtime namespace. Its original coaching workflow was exercised with bounded scenario replays, including stage pauses, clarification handling, explicit continuous execution, and evidence-limited progress. Those observations are not a controlled benchmark and private conversations are not included here.

The integrated startup instructions are also checked with three bounded replays: a missing macOS app triggers installation repair, an unsupported Linux host is reported without attempting native startup, and a complete macOS installation leads to task setup followed by Question-stage work. These are simulated agent responses, distinct from the actual fresh-install, app-signature, and CLI checks. Stage boundaries still require the user's reply by default.

The tests do not establish a general productivity benefit. They do not prove future agent compliance or continued compatibility with changing Codex desktop internals. A displayed checkpoint reflects the agent's report; assess its stated evidence against the actual deliverable.

The initial public release is checked on Apple Silicon macOS. The build script also targets Intel when run on an Intel Mac, but this release has not been independently verified on Intel hardware. The complete product requires its native HUD and local Codex on macOS 14+. Copying the Markdown instructions alone does not install the complete product.
