# Optional Live Progress HUD

The HUD supports the coaching workflow in `SKILL.md`. The assistant's project
judgment and advice determine the next action; the display reflects reported work.
When the user explicitly invokes this skill for project work, initialize/open a
separate session when the HUD is enabled and available. Use an existing session
on later turns. Mere mention or an internal method review does not opt unrelated
tasks in. If the user opts out or the HUD is unavailable, continue coaching.

This installation selects English for new HUD report reasons unless otherwise
requested. Coach in the user's conversation language. Existing titles and reasons
remain as recorded; CLI identifiers and JSON fields use fixed English values.
HUD reports do not replace project verification or required deliverables.

## Coaching pace and stage events

**Default: coach one stage, then wait.** Follow the visible-coaching and completion
contract in `SKILL.md`. State the tracked scope, current step and its completion
condition before work. Explain the stage's recommendation and result before its
HUD transition. At completion, report only that completed stage, leave the next
pending, and end the response with the closeout and next proposed step. Wait for
the user's reply before starting downstream work. A within-stage choice does not
authorize later stages, and a clarification does not automatically advance one.

Retain the scope, current step, coaching advice, stage evidence and next move in
the final response. Commentary may collapse; hover text and CLI reasons do not
replace that final record. Every checkmark must be understandable from it.
Identify design-level results explicitly. Proposed replacements and structural
checks do not establish runtime success. Keep unresolved checkpoints active, or
blocked when an actual prerequisite prevents work. Stages outside the requested
deliverable remain pending with a scope explanation; missing measurements alone
do not justify completing Accelerate or Automate as "no change needed."

**Continuous execution requires an explicit request**, such as proceeding through
the stages without waiting. Then continue authorized work from supported
checkpoints, including within one turn, while retaining every closeout in the
final record. Respect a later return to checkpoint pauses. If the user also wants
to practice the reasoning personally or answer one question at a time, wait for
their judgment within the stage. The default boundary pause leaves a red breathing
dot and "Waiting for your prompt"; an actual stage start gains a rotating ring.

Questions about a stage, hovering an icon, or elapsed time do not advance it.
Clarifications stay with the current work. Reopen an earlier stage when new
evidence invalidates its checkpoint, which clears dependent later states; simply
mentioning an earlier principle is not a reopening. Use `blocked` only when a
necessary input or external condition prevents active work. Ordinary Question-stage
inquiry or a deliberate teaching pause does not itself mean blocked.

When skipping unfinished work, the ordering reminder and subsequent confirmation
below still apply. Preserve required deliverables. The assistant interprets user
intent and reports actual starts and verified results through the CLI; the HUD
does not interpret conversation or coach independently. Never mark work complete
solely because an advice message was sent.

## Setup and reopening

Resolve the skill directory from the SKILL.md being used. Run its installed
`scripts/five_step.py` with Python 3.9 or newer. These examples use the default
personal installation; adjust the absolute skill path if installed elsewhere.

```sh
python3 "$HOME/.codex/skills/work-like-musk/scripts/five_step.py" setup \
  --project "$PWD" --title "A concise title for the current task"
```

`setup` creates the current task's session, or preserves and reopens an existing
one. It opens the progress UI without resetting progress. `--no-open` only
initializes/validates the state. The task ID defaults exclusively to
`CODEX_THREAD_ID`; if unavailable, obtain the actual task ID and pass `--task`.
Do not guess an ID, use a shared placeholder, or borrow another task's session.

At the start of every relevant turn and before a report, run `show` for this task:

```sh
python3 "$HOME/.codex/skills/work-like-musk/scripts/five_step.py" show --project "$PWD"
```

If no session exists and the user invoked this skill or requested HUD setup,
run `setup`; otherwise leave it absent. A new session has all steps pending and
Question ready. Report Question as `in_progress` when requirements work actually
begins, including asking the first relevant question. Never copy another task's
progress, infer completion from an existing project, or fill in invented history.

Sessions use canonical project paths and task IDs. Opening registers a session;
it does not make a background task take over the visible bar. The helper checks
the focused task header against the local task index, resolves a unique ID, and
shows only that task's registered session. Switching to an unregistered task,
unknown/ambiguous title, or an unreadable session hides progress immediately on
the next refresh. Duplicate titles are not guessed. Existing task names are
preserved; independently registered sessions survive app restart.
If an old project session has been removed, its missing path no longer blocks a
remaining registered session for that task. Two existing paths remain ambiguous.

## Report actual stage events

Use ordered IDs `question`, `delete`, `simplify`, `accelerate`, `automate`.
Ordinary reports are `in_progress`, `completed`, and `blocked`.
Include a concrete, trimmed English reason of at most 300 characters:

For completion, include the scoped checkpoint and observed evidence in that
reason, consistent with the closeout already explained to the user. A broad
"draft complete" reason is insufficient for an operational checkpoint.

```sh
python3 "$HOME/.codex/skills/work-like-musk/scripts/five_step.py" update \
  --project "$PWD" --stage question --status in_progress \
  --expected-revision 1 \
  --reason "Checking the requested deliverables and existing project constraints"
```

Replace `1` with the revision just returned by `show`; do not hard-code it.
If the revision changed, re-read and reconcile with the user's latest request.
Never retry an old completion with a new revision merely to force it through.
Report starts before the work, completions after verification, and reopenings
before revisiting earlier work. Inspect the returned stage/revision; the HUD
renders these explicit reports, not a semantic transcript parser.

- Start a stage when that work actually begins. Complete it only when its
  checkpoint is supported by evidence. Completion does not start the next stage.
- Complete or obtain confirmed skips for preceding stages before advancing. `completed`
  requires an active or blocked stage. Do not skip unfinished required work.
- Use `blocked` for a concrete missing input or external condition preventing
  that stage, then report `in_progress` when work resumes.
- A stage can conclude that no change is warranted after actually examining it.
  Record that examination as completed; do not invent a removal or speedup.
- Reopen an earlier stage when premises change. Reporting `in_progress` or
  `blocked` clears every later stage to pending, removing stale completion claims.
- On first setup during existing work, report established stage results only
  when current evidence supports them; do not invent a history to fill the UI.
- Keep updates to meaningful stage events. Do not generate timer updates or
  estimated percentages. Identical repeated reports preserve their timestamp.
- A report failure is not project failure: surface the concrete issue briefly,
  preserve the state, and continue independent work. Never overwrite invalid
  state, silently reset it, or write raw JSON as a fallback.

## Jumping ahead and returning to earlier work

If the user asks to jump from Question to Simplify while Delete is unfinished:

1. Keep Delete pending. Explain briefly that deleting unnecessary work first
   avoids simplifying or speeding up work that should be removed. Recommend
   doing Delete, then ask whether they still want to skip it. Do not do the
   downstream work while awaiting the answer.
2. Record that reminder using `request-skip --stage delete --to simplify
   --reason "The reminder actually presented" --expected-revision N`, with the
   usual `--project` and current `--task`. Save the returned `skipRequest.requestId`.
   This command does not advance any stage.
3. Only after the user's subsequent confirmation, call `confirm-skip
   --request-id ID --reason "Evidence of the user's confirmation after the reminder"
   --expected-revision N`. It records the skipped stages atomically, leaving
   Simplify pending. Then start Simplify with a fresh revision when work begins.
4. If the user accepts the recommendation, start Delete normally instead. That
   new report invalidates the old skip request. If they return to Delete after
   beginning Simplify, reopen Delete; all later stages reset to pending and the
   flow indicator moves back. Re-check later results before reporting them again.

Apply the same sequence to any unfinished stages being jumped over. An earlier
skip confirmation does not authorize skipping again after a stage is reopened.
Direct `update --status skipped` is rejected. Confirmation records and revision
checks enforce state transitions; the agent must faithfully report the user's
intent and must not fabricate a confirmation.

## Window and persistence

The standalone macOS accessory app defaults to a transparent, locked strip beside
the task title's three-dot button. Enable Title Tracking in Settings and grant
Five Step HUD macOS Accessibility permission to identify the foreground task.
It reads only the task header and toolbar geometry, then task names/IDs from the
local Codex index, and does not read chat contents or change host controls. Missing
permission or uncertain identity hides progress in every placement. Insufficient
title space may fall back to the menu bar only after the task is verified.

Each stage retains its own symbol: a question bubble, scissors, converging lines,
a lightning bolt, and repeat arrows. An active stage has a rotating ring; only the
next eligible pending stage has a red breathing dot. Completed stages have a small
checkmark; blocked stages show an amber exclamation mark. Reduce Motion uses static
equivalents. The strip background is clear unless increased contrast or reduced
transparency requests an accessible solid surface. Hover for the task title,
status, full reason, and timestamp. Switching away from Codex hides progress.

Only the connector entering the next pending or currently active stage has a
left-to-right particle. Earlier and future connectors remain static. Question
has no incoming connector, so a fresh session has no moving line. Blocking,
completion, and read errors stop flow; Reduce Motion retains static lines.

Open Settings with the separate rounded button on the right or the bar's right-click menu.
While the HUD's controls have focus, the bar is hidden and Settings labels any
retained context as the last verified task. Returning to Codex verifies its task
again before showing progress; Settings is not proof of the current host task.
Show Progress In selects Beside Task Title, Menu Bar, or Floating Bar. Allow
Dragging is off by default; enabling it exposes a left handle and saves the
adjusted position while following the window. Turning it off restores title
anchoring. Restore Default Position restores locked title placement without
clearing Appearance or Accent Color. Close preserves state; reopen with:

```sh
python3 "$HOME/.codex/skills/work-like-musk/scripts/five_step.py" open --project "$PWD"
```

State lives at `<project>/.work-like-musk/sessions/<sha256(task ID)>.json` and
survives restarts. Avoid committing this per-task runtime state; honor the
project's existing ignore policy. Skip reminders are stored in a companion
`.skip.json` bound to the exact task and revision. Read errors hide the bar to
avoid presenting stale progress. Accessibility is requested only when the user selects Enable
Title Tracking; no background login item is installed.
The CLI rejects linked runtime directories and non-regular state, request, or
lock files without replacing them. Preserve such files and resolve their origin;
do not work around the error by writing raw state.
macOS permission windows and the native color panel use the system language.
