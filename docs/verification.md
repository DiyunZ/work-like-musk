# Verification scope

Implementation checks are reproducible through the commands in the README and the [repository CI workflow](../.github/workflows/checks.yml).

The cross-platform implementation at `8a60acd` passed [all five CI jobs](https://github.com/DiyunZ/work-like-musk/actions/runs/34071332204):

| Runner | Observed result |
| --- | --- |
| Windows / Python 3.12 | 84 Python tests passed; 23 macOS/POSIX-only tests skipped; complete portable installation passed. |
| Linux / Python 3.12 | 84 Python tests passed; 23 macOS/Windows-only tests skipped; complete portable installation passed. |
| Linux / Python 3.9 | 84 Python tests passed; 23 macOS/Windows-only tests skipped; complete portable installation passed. |
| macOS / Python 3.12 | 106 Python tests passed; one Windows-only test skipped; complete portable installation passed. |
| Native macOS | Eight native test suites, automatic build, complete installation, and strict signature verification passed. |

All 24 Qt GUI tests ran successfully on each Python runner, including the visible-window transparency capture and all five rendering scales. Local macOS checks also ran 107 Python tests with only the Windows-specific test skipped. Final review found a Wayland drag API issue; the corrected compositor call and preserved stage clicks have a regression test, while physical Wayland interaction remains unverified.

| Area | Checks |
| --- | --- |
| Python state CLI | Task isolation, explicit host IDs or generated local IDs, ordered transitions, reopening, revision conflicts, confirmed skips, Unicode-safe output, and protected runtime files. |
| Shared runtime | Actual child-process locks, bounded startup, correct task identity in success and failure output, startup error recovery, and canonical temporary paths. |
| Portable installer | Complete installation for each agent preset, private Qt environment preparation, independent GUI interpreter selection, saved language/backend, customized guidance, backup/rollback, and transaction ownership across agent and backup-root changes. |
| Portable HUD | Real Qt windows, task binding, independent sessions, readiness without stage advancement, hover behavior, corrupt-state clearing, writer/read coordination, and concurrent startup success/failure. |
| Native HUD | State decoding, task identity, placement, preferences, localization, stage readiness, and interaction behavior. |
| Native installation/build | Automatic Swift build with warnings treated as errors, complete installation, macOS file metadata preservation, and ad-hoc signing. |

The public package renames the existing skill and runtime namespace. Its original coaching workflow was exercised with bounded scenario replays, including stage pauses, clarification handling, explicit continuous execution, and evidence-limited progress. Those observations are not a controlled benchmark and private conversations are not included here.

The cross-platform startup instructions were checked with bounded before/after replays for Windows/Claude Code, Linux/Gemini CLI, and macOS/Cursor. The old instructions rejected those hosts. The updated instructions select the portable HUD, resolve the actual loaded skill directory, and retain an actual host ID or one generated tracking ID. A failed-startup case retains the identity and retries that same session after repair. These are simulated agent responses, distinct from real installation and GUI execution. The replay also checks stage pauses, clarification handling, and explicit continuous execution.

The CI matrix requires a working Qt runtime and visible widget before running the Python suite on Windows, Linux under Xvfb with xcompmgr, and macOS. A separate Linux job exercises the Python 3.9 floor; native Swift checks and signed installation run on macOS. POSIX FIFO tests and macOS-specific metadata tests remain platform-specific. Linux Xvfb results verify GUI behavior in a composited virtual display, not interaction with a physical desktop. Wayland and every multi-monitor hardware configuration are not covered by that X11 job.

Qt tests render the actual widget at 1×, 1.25×, 1.5×, 1.75×, and 2×, checking transparent gaps, partially covered antialiased edges, and opaque icon strokes. A separate test captures the visible HUD over its own synthetic background and checks the resulting pixels; Windows/Linux fail if that capture is unavailable. macOS can report a capture skip when system screen-recording access prevents it.

The native macOS HUD is the visual reference for the portable strip's geometry, stage symbols, state badges, colors, and motion. Portable symbols use original artwork. A matching design contract and behavior tests do not establish pixel-for-pixel equality of operating-system text rendering, display scaling, or window-manager composition.

The named agents' published discovery interfaces are documented in [compatibility](compatibility.md). Runtime tests and simulated instruction replays do not mean every agent application/version has been operated end to end. The tests do not establish a general productivity benefit, future agent compliance, or continued compatibility with changing Codex desktop internals. A checkpoint reflects the agent's report; assess its evidence against the actual deliverable.

The native build targets the machine's architecture. Local checks use Apple Silicon macOS; Intel native hardware has not been independently verified. Copying the Markdown instructions alone does not install the complete product.
