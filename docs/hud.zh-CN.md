# 一体化实时 HUD

[English](hud.md) · [简体中文](hud.zh-CN.md) · [README](../README.zh-CN.md)

HUD 是 Work Like Musk 的内置组成部分，覆盖 Windows、Linux 桌面和 macOS，随指导 Skill 一起安装并显示 AI 报告的阶段事件。

## 安装完整产品

克隆仓库后，选择实际 agent：

```sh
python3 scripts/install.py --agent claude-code --language zh-CN
```

Windows 使用 `python`。[README 安装表格](../README.zh-CN.md#安装) 列出全部预设和目录。
通用悬浮方式需要 Python 3.9+ 和图形桌面。安装器复用合适的 Qt for Python，或下载至
`~/.work-like-musk/runtimes/` 下的独立 Python 环境，并记录 GUI 解释器，因此 agent 自带的
Python 无需安装 Qt。macOS 14+ 的 Codex 桌面原生方式
需要 Swift 命令行工具编译。Codex CLI 或希望在 macOS 使用明确绑定任务的悬浮窗时，
添加 `--hud portable`。

英文标签和报告指导使用 `--language en`。终端中不指定语言时提示选择；首次非交互安装
必须指定。升级保留已有语言和显示方式，除非明确更改。自定义目录使用
`--skill "<实际Skill目录>"`。

安装器包含指导指令、状态与锁工具、双语协议指南、配置及所选 HUD，保留自定义指导和
已有 agent 元数据。Codex 的替换备份位于 `~/.codex/skill-backups/work-like-musk-hud/`，
其他 agent 位于 `~/.work-like-musk/skill-backups/`。安装器输出具体备份路径和事务状态。
未完成的事务需要先检查，保留其恢复文件。升级后重启 HUD 以加载新版本。

## 通用悬浮窗口

通过 agent 启用 Skill 后，独立窗口显示 **任务标题、项目名和缩短的任务 ID**。
切换应用或对话时，它仍绑定原任务。不同任务各有窗口，同一任务再次打开会使用已有窗口。

248×30 的进度核心沿用 Mac 原生版的布局、状态颜色与动画，背景透明；任务标签配有小块
半透明底色以保证可读性。Qt 按逻辑尺寸绘制抗锯齿矢量图形，适配 125%、150%、175% 和
200% 缩放。文字使用系统字体。Linux 透明效果需要 Wayland 或启用合成器的 X11 桌面，
参见 [Qt 透明窗口要求](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#creating-translucent-windows)
及 [高 DPI 绘制](https://doc.qt.io/qt-6/highdpi.html)。

拖动进度条移动位置；三点菜单或右键切换置顶与减少动态效果。关闭或 Escape 只关闭窗口，
保留状态。此模式只读取指定任务的进度文件，不检查前台应用、聊天或其他任务索引，
不需要辅助功能权限。

宿主没有会话 ID 时，初始化生成一个本地跟踪 ID。agent 在本对话保留它，后续命令明确传入。
启动失败时输出的 ID 也应保留，用于修复后的重试。具体命令见
[协议指南](../skills/work-like-musk/references/live-progress.zh-CN.md)。

## 原生 Codex 标题跟随（macOS 14+）

原生方式在 Codex 桌面项目中调用 `$work-like-musk`。AI 会检查安装、为当前任务建立独立会话，并按标准流程打开 HUD。在 HUD 设置中启用标题跟随，到 **系统设置 → 隐私与安全性 → 辅助功能** 允许 HUD，然后返回 Codex。

应用读取当前任务标题及工具栏位置，再通过只读数据库查询，用完整且唯一的标题匹配本地 Codex 任务身份。它不读取聊天消息、不截屏，也不修改 Codex 控件。本项目不会安装网络服务、登录项或后台守护进程。AI 宿主有其自己的数据处理方式，与 HUD 独立。

适配依赖 Codex 的本地任务索引和可见标题结构。标题跟随不覆盖其他宿主、云端任务、重名任务和未来的 Codex 变化。其他本地 agent 使用通用悬浮方式。缺少权限或无法确认任务身份时隐藏进度；已确认任务但标题栏空间不足时，可以回退到菜单栏。设置中显示最近验证的任务和跟随状态。

## 读取进度

| 指示器 | 含义 |
| --- | --- |
| 旋转圆环 | AI 已报告正在执行当前阶段。 |
| 红色呼吸指示 | 下一可执行阶段正在等待你的指令。 |
| 完成勾选 | AI 已报告完成及其依据。 |
| 琥珀色指示 | 缺少必要输入或外部条件，工作受阻。 |

悬停可查看步骤、状态、报告说明和时间；窗口标明所属任务。悬停或点击不会启动工作。减少动态效果使用静态指示。原生设置另外提供位置、主题、颜色、缩放和对比度相关选项。

最终指导回复仍需保留工作范围和证据。视觉勾选本身不是独立验收。

## 状态与隐私

会话保存在 `<project>/.work-like-musk/sessions/`，按任务身份分别存储。状态包含项目路径、任务 ID、标题、说明和时间。它属于本地项目数据，不应进入公开提交。使用 HUD 时，请把 `.work-like-musk/` 加入项目忽略文件。

CLI 默认使用真实的 `CODEX_THREAD_ID`。其他环境用 `--task` 提供实际会话 ID，或只运行一次 `setup --new-task` 并保留返回的本地跟踪 ID。后续在本对话重复使用，不根据最近修改时间选择状态文件。报告前读取当前修订号，旧修订号会被拒绝。重开较早阶段会清除依赖它的后续状态。跳过未完成阶段前，需要先提醒顺序要求，再由用户单独确认。

命令与边界详见 [agent 协议指南](../skills/work-like-musk/references/live-progress.zh-CN.md)。不要直接修改会话 JSON 来制造想要的显示结果。

## 故障排查

- **Qt 下载或环境创建失败：** 修复报错指出的网络、包或 Python `venv` 问题后，重新运行安装器。需要时它会在独立环境安装 `PySide6-Essentials>=6.8,<7`。Python、系统及 CPU 需要有对应的 [官方安装包](https://pypi.org/project/PySide6-Essentials/)。运行环境缺失不会重置阶段进度。
- **Qt 平台插件或透明效果不可用：** 使用本地图形会话。Linux 需启用桌面合成器，未启用合成的纯 X11 无法提供所需透明效果，启动器会明确报告配置未完成。缺失的系统库以 Qt/平台错误为准，参见 [Linux Qt 依赖](https://doc.qt.io/qt-6/linux-requirements.html)。
- **没有图形显示：** 在可用的本地图形桌面运行 agent 和 Python。无显示的 SSH 或纯云端 agent 无法显示完整产品，安装成功不代表窗口已可见。
- **悬浮窗已关闭：** 要求 agent 使用保留的 `taskId` 重新打开，进度不会丢失。
- **原生面板不显示：** 返回已登记 Codex 任务，检查辅助功能权限、HUD 设置状态及标题唯一性。
- **重新编译后权限无效：** macOS 可能保留旧本地签名身份，移除旧条目并重新加入已安装的 `assets/FiveStepHUD.app`。
- **只有指令，缺少 HUD 文件：** 为相同 agent 和 Skill 目录重新运行统一安装器，再打开当前任务。配置失败保留已有进度并报告任务身份。
- **修订号过期：** 读取最新状态，重新判断事件再报告。
- **运行文件为链接或格式异常：** 保留并检查来源。CLI 拒绝操作，不直接替换。

macOS 原生隔离视觉预览使用 `python3 scripts/preview.py --language en`。它使用虚构状态，不检查其他应用。预览按钮只用于演示显示行为，不能代替真实项目工作的完成。
