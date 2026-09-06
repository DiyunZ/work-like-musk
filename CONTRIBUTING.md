# Contributing

Keep changes focused on useful project coaching or the optional local HUD. Open an issue or pull request with the problem, the proposed behavior, and the evidence that supports it.

## Local checks

The core skill is in `skills/work-like-musk/SKILL.md`. Keep its name, directory, and `agents/openai.yaml` invocation consistent. Preserve the one-stage-then-wait default unless a change is explicitly discussed.

On macOS 14+ with Python 3.9+ and Apple Swift command-line tools:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/test_native.py
python3 scripts/build.py
```

The state CLI tests can also run on Linux:

```sh
python3 -m unittest discover -s tests -p 'test_progress.py' -v
```

When changing coaching behavior, include a concrete before/after scenario. Check at least a normal checkpoint, a clarification that should not advance stages, and an explicit request for continuous work. Label simulated responses separately from actual project execution. Passing implementation tests alone does not prove the quality of a prompt change.

## Public examples

Use synthetic task titles and content. Do not include chat exports, local session state, absolute home paths, credentials, or personal screenshots. Keep text inside screenshots, diagrams, and posters in English. Maintain the English and Simplified Chinese READMEs together.

The installer has backup and ownership checks. Preserve those checks when changing installation behavior. Never test an installer change against your only copy of a customized skill.
