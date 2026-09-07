<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>

# Work Like Musk

**让 AI agent 带着五步教练的判断力开展项目。**

Work Like Musk 用 **质疑需求 → 删除 → 简化 → 加速 → 自动化** 指导项目工作。在投入工作前，AI 会审视自己的方案，解释一条具体建议，付诸行动，再用结果检验判断。

指导直接发生在对话中。**默认每完成一步，都等你回应。** 你也可以明确要求连续推进，或自己练习判断。

## 为什么使用它？

- **尽早发现多余工作。** 先追问需求为什么存在，再围绕它实现。
- **看懂背后的判断。** 每条关键建议都有理由、下一步行动和验证方式。
- **自己掌握节奏。** 当前步骤完成后，下一步保持待开始，直到你继续。
- **让结果可检查。** 最终回复保留交付物、证据、未解决的问题和下一步。

## 安装

Skill 由 Markdown 指导和可选的 Codex 界面元数据组成。使用它需要宿主能够加载 Agent Skills；执行项目还需要对应工具和授权。

安装器仅使用 **Python 3.9+ 和标准库**：

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/install.py --agent claude-code
```

Windows / PowerShell 将 `python3` 换为 `python`。

| `--agent` | 用户主目录下的安装位置 | 启动方式 |
| --- | --- | --- |
| `codex` | `.codex/skills/work-like-musk` | `$work-like-musk` |
| `claude-code` | `.claude/skills/work-like-musk` | `/work-like-musk` |
| `cursor` | `.cursor/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `gemini-cli` | `.gemini/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `opencode` | `.config/opencode/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `generic` | `.agents/skills/work-like-musk` | 通过宿主支持的 Skill 方式启用 |

安装后重启 agent 或重新加载 Skills。不指定 agent 时默认为 Codex。OpenCode 遵循 `XDG_CONFIG_HOME`。自定义或项目级目录使用 `--skill "<实际Skill目录>"`。详见[兼容范围与宿主参考](docs/compatibility.md)。

同一命令也用于升级，保留自定义指导、调用策略和支持的文件元数据。被修改的文件会备份到 Skill 目录之外，命令会输出备份位置。存在未完成的安装事务时，需要先检查再升级。

**从 HUD 版本升级：** 安装器移除旧的 HUD 托管指令，并备份、移除已知的应用、脚本、指南和配置文件；保留自定义文件和项目会话数据。请关闭仍在运行的旧 HUD。Skill 目录外的共享环境保持原状。安装时不再传入旧的 `--hud`、`--app` 或 `--language` 参数；指导跟随对话语言。

## 开始使用

```text
$work-like-musk
帮我做一个把 CSV 文件转换为周报的小工具。
每次指导并完成一个步骤，等我回应后再进入下一步。
```

其他 agent 按表格调用。AI 首先明确真实目标及 **质疑需求** 这一步的验收条件。它可以在当前阶段检查项目、执行已授权的工作。针对当前结果的追问不会自动开启后续阶段。

一次阶段收尾可以这样表达：

> **01 · 质疑需求 — 已完成**
>
> 当前需要的是从一个 CSV 生成一份本地报告。仪表盘和定时服务属于实现选择，先验证它们有没有必要，再决定是否实现。
>
> **证据：** 已明确输出、输入格式和验收方式；尚未验证运行效果。
>
> **下一步：** 检查哪些部分可以删除。第 02–05 步仍待开始。回复“继续删除步骤”后推进。

这是虚构的指导示例，不是 Musk 原话或真实用户对话。

## 五个步骤，每一步都有推进依据

| 步骤 | 核心问题 | 需要寻找的证据 |
| --- | --- | --- |
| **01 质疑需求** | 这个需求解决什么问题？ | 明确的目标、来源、约束和验收方式。 |
| **02 删除** | 这个部分能完全去掉吗？ | 可恢复的试验，证明可以删除或应当保留。 |
| **03 简化** | 完整实现目标的最小路径是什么？ | 可用的端到端结果，以及必要检查。 |
| **04 加速** | 时间到底花在哪里？ | 观察到的瓶颈，以及相关指标的前后对比。 |
| **05 自动化** | 这件事值得自动重复吗？ | 稳定的操作、值得投入的收益和经过验证的失败处理。 |

新证据推翻旧判断时，Skill 会重开较早的步骤。设计层面的完成只表示设计进展；运行效果需要实际运行证据。超出本次范围的阶段保持待开始。五步法用于做决策，不要求凭空凑出五项修改。

## 选择你的节奏

| 你希望…… | 可以这样说 |
| --- | --- |
| 每步停下来 **（默认）** | “完成这一步，说明证据，然后等我。” |
| 连续推进 | “各步骤之间不用等待，最后保留每一步的结论和证据。” |
| 自己练习判断 | “一次只问我一个问题，让我自己推理。” |

指导会跟随对话语言。`SKILL.md` 本身使用英文。

## 仓库与检查

```text
skills/work-like-musk/   教练指导与 agent 元数据
scripts/install.py      安装器及旧 HUD 版本迁移
tests/                  安装、迁移和恢复检查
docs/                   兼容性和验证范围
```

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

CI 矩阵覆盖 Windows、Linux、macOS 及最低 Python 版本，不需要 GUI 依赖。实现检查不代表已证明普遍的效率提升，也不保证 agent 每次都完全遵循 Skill。详见[验证范围](docs/verification.md)和[贡献指南](CONTRIBUTING.md)。

## 来源与许可

五步顺序来自 [Everyday Astronaut 对 2021 年 Elon Musk 访谈的总结](https://everydayastronaut.com/starbase-tour-and-interview-with-elon-musk/)。指导循环、阶段停顿、证据规则及 agent 集成为本项目的改编。

本项目独立开发，与 Elon Musk、其公司或 OpenAI 无隶属或代言关系。[MIT 许可](LICENSE)在权利存在的范围内适用于项目材料，不授予第三方姓名、肖像或代言权。
