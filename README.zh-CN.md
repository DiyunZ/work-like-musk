<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>

![Work Like Musk — five-step coaching for AI agents](docs/assets/work-like-musk-hero.png)

<p align="center"><strong>让 AI agent 带着教练的判断力工作，用实时进度条看清每一步。</strong></p>
<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="skills/work-like-musk/SKILL.md"><img alt="Agent Skill" src="https://img.shields.io/badge/Agent-Skill-635BFF?style=flat-square&labelColor=171717"></a>
  <a href="docs/hud.zh-CN.md"><img alt="Windows · Linux · macOS" src="https://img.shields.io/badge/HUD-Windows_%7C_Linux_%7C_macOS-635BFF?style=flat-square&labelColor=171717"></a>
</p>

**Work Like Musk** 将 AI 项目教练与进度 HUD 整合为同一产品，覆盖 Windows、Linux 桌面和 macOS，用 **质疑需求 → 删除 → 简化 → 加速 → 自动化** 指导 AI 开展项目。在投入工作前，AI 会审视自己的方案，解释一条具体建议，付诸行动，再用结果检验判断。

**默认每完成一步，都等你回应。** 需要时，你也可以明确要求连续推进。

## 为什么使用它？

- **尽早发现多余工作。** 先追问需求为什么存在，再围绕它实现。
- **看懂背后的判断。** 每条关键建议都有理由、下一步行动和验证方式。
- **自己掌握节奏。** 当前步骤完成后，下一步保持待开始，直到你继续。
- **看清进度属于哪个任务。** 内置 HUD 显示当前阶段，最终回复保留工作范围、证据、未解决的问题和下一步。

## 安装

通用悬浮 HUD 需要 **Python 3.9+** 和图形桌面。本地 agent 需要能加载 Agent Skills 并执行命令。统一安装器一次安装指导 Skill、进度工具和 HUD，并自动准备 Qt 运行环境。尚未安装 Qt 时，首次安装通用版需要联网下载依赖。

```sh
git clone https://github.com/DiyunZ/work-like-musk.git
cd work-like-musk
python3 scripts/install.py --agent claude-code --language zh-CN
```

**Windows / PowerShell** 使用：

```powershell
python scripts/install.py --agent claude-code --language zh-CN
```

按实际 agent 选择参数；预设使用其官方文档中的个人 Skill 目录：

| `--agent` | 用户主目录下的安装位置 | 启动方式 |
| --- | --- | --- |
| `codex` | `.codex/skills/work-like-musk` | `$work-like-musk` |
| `claude-code` | `.claude/skills/work-like-musk` | `/work-like-musk` |
| `cursor` | `.cursor/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `gemini-cli` | `.gemini/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `opencode` | `.config/opencode/skills/work-like-musk` | 要求使用 `work-like-musk` |
| `generic` | `.agents/skills/work-like-musk` | 通过宿主的 Skill 加载方式启用 |

安装后重启 agent 或重新加载 Skills。OpenCode 遵循 `XDG_CONFIG_HOME`。自定义或项目级目录使用 `--skill "<实际Skill目录>"`。其他 agent 需要具备兼容的 Skill 加载与本地命令能力；`generic` 不会替宿主补充这些功能。详见 [兼容范围与官方参考](docs/compatibility.md)。

英文界面及报告指导使用 `--language en`。不指定 agent 时默认为 Codex。**macOS 14+ 的 Codex 桌面**默认编译现有原生标题跟随 HUD，需要 Apple Swift 命令行工具，此方式不要求 Qt。Codex CLI 或希望在 macOS 使用悬浮窗时，加上 `--hud portable`。

同一命令也用于升级，保留语言、显示方式和自定义指导，并备份替换的文件。升级后重启 HUD 以加载新版本。缺少 HUD 代表配置尚未完整，需要修复。运行检查及恢复方法见 [HUD 指南](docs/hud.zh-CN.md)。

## 开始使用

```text
$work-like-musk
帮我做一个把 CSV 文件转换为周报的小工具。
每次指导并完成一个步骤，等我回应后再进入下一步。
```

其他 agent 按表格调用，或直接要求“使用 work-like-musk”。AI 首先检查安装、启动当前任务的 HUD，再明确真实目标及 **质疑需求** 这一步的验收条件。它可以在当前阶段检查项目、执行已授权的工作。针对当前结果的追问不会自动开启后续阶段。

一次阶段收尾可以这样表达：

> **01 · 质疑需求 — 已完成**
>
> 当前需要的是从一个 CSV 生成一份本地报告。仪表盘和定时服务属于实现选择，先验证它们有没有必要，再决定是否实现。
>
> **证据：** 已明确输出、输入格式和验收方式；尚未验证运行效果。
>
> **下一步：** 检查哪些部分可以删除。第 02–05 步仍待开始。回复“继续删除步骤”后推进。

这是虚构的指导示例，用于展示预期表达方式，不是 Musk 原话或真实用户对话。

## 五个步骤，每一步都有推进依据

| 步骤 | 核心问题 | 需要寻找的证据 |
| --- | --- | --- |
| **01 质疑需求** | 这个需求解决什么问题？ | 明确的目标、来源、约束和验收方式。 |
| **02 删除** | 这个部分能完全去掉吗？ | 可恢复的试验，证明可以删除或应当保留。 |
| **03 简化** | 完整实现目标的最小路径是什么？ | 可用的端到端结果，以及必要检查。 |
| **04 加速** | 时间到底花在哪里？ | 观察到的瓶颈，以及相关指标的前后对比。 |
| **05 自动化** | 这件事值得自动重复吗？ | 稳定的操作、值得投入的收益和经过验证的失败处理。 |

新证据推翻旧判断时，Skill 会重开较早的步骤。设计层面的勾选只表示设计进展；运行效果需要实际运行证据。超出本次范围的阶段保持待开始。五步法用于做决策，不要求凭空凑出五项修改。

## 选择你的节奏

| 你希望…… | 可以这样说 |
| --- | --- |
| 每步停下来 **（默认）** | “完成这一步，说明证据，然后等我。” |
| 连续推进 | “各步骤之间不用等待，最后保留每一步的结论和证据。” |
| 自己练习判断 | “一次只问我一个问题，让我自己推理。” |

可以用中文或英文交流，指导会跟随对话语言。`SKILL.md` 本身使用英文。

## 看清进度绑定的任务

通用 HUD 是可拖动的悬浮条，明确显示 **任务标题、项目和任务标识**。切换应用或对话时，它仍绑定原任务；不同任务可以有独立窗口。宿主不提供会话 ID 时，会创建唯一的本地跟踪 ID，并在当前对话中持续使用。

进度核心沿用 Mac 原生版的紧凑布局、颜色、状态标记和动画节奏，背景真正透明。矢量绘制适配高分辨率屏幕及非整数缩放。Linux 需要启用桌面合成，详见 [兼容性说明](docs/compatibility.md)。

- 旋转圆环表示正在执行；红色呼吸指示表示下一阶段等待你的指令。
- 悬停查看报告说明和时间，菜单控制置顶与减少动态效果。
- 完成标记跟随 AI 提供的证据，面板本身不会独立验证项目。
- 使用本地文件与 GUI 运行环境；HUD 不需要网络服务或 API key。

macOS/Codex 原生方式另外提供经过任务核验的标题跟随、菜单栏位置和外观设置。首次使用时，在 HUD 设置中启用跟随并授予 macOS 辅助功能权限。适配依赖 Codex 本地任务元数据，可能需要随 Codex 更新调整。原生应用在本地编译和临时签名。

每个已启用的项目会话都包含 HUD。无图形桌面的终端、没有显示转发的 SSH 和纯云端 agent 无法在本地显示完整产品。

## 仓库内容

```text
skills/work-like-musk/   Coaching instructions, protocol, state CLI, and portable HUD
native/                 macOS/Codex SwiftUI/AppKit HUD
scripts/                Unified product installer, build, preview, and test runner
tests/                  State, installer, portable GUI, and native regression checks
docs/                   HUD guide and original English artwork
```

使用具备 Qt 的 Python 和图形桌面执行检查，Windows 将 `python3` 换为 `python`：

```sh
python3 -m pip install 'PySide6-Essentials>=6.8,<7'
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Linux CI 使用 Xvfb 和窗口合成器，本地命令见 [贡献指南](CONTRIBUTING.md)。macOS 原生方式还运行 `python3 scripts/test_native.py` 和 `python3 scripts/build.py`。CI 覆盖 Windows、Linux、macOS 及最低 Python 版本。

这些检查验证实现行为，不代表已证明普遍的效率提升，也不保证 agent 每次都完全遵循 Skill。详见 [验证范围](docs/verification.md) 和 [贡献指南](CONTRIBUTING.md)。

## 来源与许可

五步顺序来自 [Everyday Astronaut 对 2021 年 Elon Musk 访谈的总结](https://everydayastronaut.com/starbase-tour-and-interview-with-elon-musk/)。指导循环、阶段停顿、证据规则及 agent 集成为本项目的改编。

本项目独立开发，与 Elon Musk、其公司或 OpenAI 无隶属或代言关系。[MIT 许可](LICENSE) 在权利存在的范围内适用于项目材料，不授予第三方姓名、肖像或代言权。

通用 HUD 使用从官方包独立安装的 Qt for Python，许可与源码见 [第三方声明](THIRD_PARTY_NOTICES.md)。
