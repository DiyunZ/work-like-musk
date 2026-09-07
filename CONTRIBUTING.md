# Contributing

Keep changes focused on the integrated project coaching and local HUD experience. Open an issue or pull request with the problem, the proposed behavior, and the evidence that supports it.

## Local checks

The core skill is in `skills/work-like-musk/SKILL.md`. Keep its name, directory, and `agents/openai.yaml` invocation consistent. Preserve the one-stage-then-wait default unless a change is explicitly discussed.

Use Python 3.9+ with Qt and a graphical desktop (`python` on Windows). A development venv keeps the dependency separate from system Python:

```sh
python3 -m pip install 'PySide6-Essentials>=6.8,<7'
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

On Linux without a visible desktop, install Xvfb, xauth, xcompmgr, and the Qt platform libraries listed in the CI workflow, then run with composition enabled:

```sh
xvfb-run -a -s '-screen 0 1280x720x24' bash -e -c '
  xcompmgr &
  compositor_pid=$!
  trap "kill $compositor_pid" EXIT
  sleep 1
  python3 -m unittest discover -s tests -p "test_*.py" -v
'
```

The native backend additionally requires macOS 14+ and Swift command-line tools. Run `python3 scripts/test_native.py` and `python3 scripts/build.py` there. CI requires an imported Qt runtime and a visible Qt widget before the Python suite so missing Qt cannot silently turn the GUI gate into a skip. POSIX FIFO checks and macOS metadata checks remain platform-specific.

Keep the portable strip aligned with the native HUD's layout, symbols, state badges, colors, and motion. Use original portable artwork. Verify transparent pixels, antialiased edges, and vector rendering at 1×, 1.25×, 1.5×, 1.75×, and 2×. Keep task identity visible and confirm that completing a stage does not start the next one.

When changing coaching behavior, include a concrete before/after scenario. Check at least a normal checkpoint, a clarification that should not advance stages, and an explicit request for continuous work. Label simulated responses separately from actual project execution. Passing implementation tests alone does not prove the quality of a prompt change.

## Public examples

Use synthetic task titles and content. Do not include chat exports, local session state, absolute home paths, credentials, or personal screenshots. Keep text inside screenshots, diagrams, and posters in English. Maintain the English and Simplified Chinese READMEs together.

The installer has backup and ownership checks. Preserve those checks when changing installation behavior. Never test an installer change against your only copy of a customized skill.
