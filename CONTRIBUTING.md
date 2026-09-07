# Contributing

Keep changes focused on five-step project coaching. Open an issue or pull request with the problem, proposed behavior, and supporting evidence.

## Local checks

The core skill is in `skills/work-like-musk/SKILL.md`. Keep its name, directory, and `agents/openai.yaml` invocation consistent. Preserve the one-stage-then-wait default unless a change is explicitly discussed.

Use Python 3.9+ (`python` on Windows). The installer and tests use only the standard library:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

When changing coaching behavior, include a concrete before/after scenario. Check a normal checkpoint, a clarification that should not advance stages, and an explicit request for continuous work. Label simulated responses separately from actual project execution. Passing installation tests does not prove the quality of coaching.

The installer preserves custom guidance, invocation policy, symlinks, and supported metadata. Keep backup, rollback, locking, and unfinished-transaction checks. Migration removes only the known former HUD files inside a recognized installation, after backing them up. Never test an installer change against your only copy of a customized skill.

## Public examples

Use synthetic task titles and content. Do not include chat exports, local session state, absolute home paths, credentials, or personal screenshots. Keep text inside visuals in English. Maintain the English and Simplified Chinese READMEs together.
