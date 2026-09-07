# Compatibility

Work Like Musk consists of `SKILL.md` and supplemental `agents/openai.yaml` metadata. Coaching runs in the host conversation. The host must load Agent Skills and provide the tools and authorization needed for the requested project work.

The optional installer uses Python 3.9+ and the standard library on Windows, Linux, and macOS. A graphical desktop, Qt, Swift, and accessibility permissions are no longer prerequisites. The skill files themselves do not require Python at runtime.

## Agent discovery

The installer presets follow the hosts' documented personal skill directories. Host versions and policies can change; a directory contract is distinct from an end-to-end run inside each agent application.

| Preset | Host documentation |
| --- | --- |
| `codex` | [Codex Agent Skills](https://developers.openai.com/codex/skills/) |
| `claude-code` | [Claude Code Skills](https://code.claude.com/docs/en/skills) |
| `cursor` | [Cursor Agent Skills](https://cursor.com/docs/skills) |
| `gemini-cli` | [Gemini CLI Skills](https://geminicli.com/docs/cli/skills/) |
| `opencode` | [OpenCode Skills](https://opencode.ai/docs/skills/) |
| `generic` | A host that discovers `.agents/skills`, or a custom directory supplied with `--skill` |

Codex-specific `agents/openai.yaml` is supplemental metadata; the shared skill uses `name` and `description` frontmatter and Markdown instructions. Use each host's supported invocation or ask it to use `work-like-musk`. OpenCode follows `XDG_CONFIG_HOME` when set.

A headless or cloud environment can use the coaching instructions if its host supports loading them and the necessary project tools. This is not a claim that every cloud product provides Skill installation or that every agent version has been operated end to end. See [verification scope](verification.md).
