import Foundation

enum HUDLanguage: String, CaseIterable {
    case english = "en"
    case chinese = "zh-CN"

    var locale: Locale { Locale(identifier: rawValue) }

    static func load(from url: URL) -> HUDLanguage {
        guard let data = try? Data(contentsOf: url),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: String],
              Set(object.keys) == ["language"], let value = object["language"],
              let language = HUDLanguage(rawValue: value) else { return .english }
        return language
    }

    func text(_ english: String) -> String {
        guard self == .chinese else { return english }
        let unreadablePrefix = "Unable to read session: "
        if english.hasPrefix(unreadablePrefix) {
            return "无法读取会话：" + english.dropFirst(unreadablePrefix.count)
        }
        return Self.translations[english] ?? english
    }

    // English source strings remain stable keys. User-authored titles and
    // historical reasons are displayed verbatim, never passed through this map.
    static let translations: [String: String] = [
        "Five Step": "五步工作法",
        "Five Step progress": "五步进度",
        "Step details": "步骤详情",
        "Five Step Settings": "五步工作法设置",
        "Settings": "设置",
        "Settings…": "设置…",
        "Position": "位置",
        "Last verified task": "上次核验的任务",
        "Return to Codex to verify its current task and show progress.": "返回 Codex 后，会重新核验当前任务并显示进度。",
        "No verified Five Step task is visible. Progress is hidden.": "当前未显示已核验的五步任务，进度条已隐藏。",
        "Allow Five Step HUD in macOS Accessibility to identify the current task. Progress is hidden.": "请在 macOS 辅助功能中允许 Five Step HUD 识别当前任务。进度条已隐藏。",
        "The current task cannot be identified uniquely. Progress is hidden.": "无法唯一识别当前任务，进度条已隐藏。",
        "This task has no readable Five Step session. Progress is hidden.": "此任务没有可读取的五步进度会话，进度条已隐藏。",
        "Showing progress for the verified current task.": "正在显示已核验的当前任务进度。",
        "Show Progress In": "进度显示位置",
        "Beside Task Title": "任务标题旁",
        "Menu Bar": "菜单栏",
        "Floating Bar": "悬浮条",
        "Allow Dragging": "允许拖动",
        "Off by default. Unlocking lets you drag the left handle; locking restores the title anchor.": "默认关闭。开启后可拖动左侧手柄；关闭后恢复跟随任务标题。",
        "Restore Default Position": "恢复默认位置",
        "Enable Title Tracking…": "启用标题跟随…",
        "Requires macOS Accessibility permission. Reads the task header and toolbar geometry, then checks local task names and IDs; no chat content.": "需要 macOS 辅助功能权限。仅读取任务标题、工具栏位置，并核对本地任务名称与标识，不读取聊天正文。",
        "Appearance": "外观",
        "System": "跟随系统",
        "Light": "浅色",
        "Dark": "深色",
        "Accent Color": "强调色",
        "Use blue accent": "使用蓝色强调色",
        "Use green accent": "使用绿色强调色",
        "Use purple accent": "使用紫色强调色",
        "Use orange accent": "使用橙色强调色",
        "Use pink accent": "使用粉色强调色",
        "Hover over a step for details. Right-click the progress bar to open settings.": "将鼠标移到步骤上查看详情。右键点击进度条可打开设置。",
        "Move progress bar": "移动进度条",
        "Drag to position · Right-click for options": "拖动以调整位置 · 右键查看选项",
        "Settings · Position is locked": "设置 · 位置已锁定",
        "Settings · Position is unlocked": "设置 · 位置已解锁",
        "Close progress bar": "关闭进度条",
        "Question": "质疑需求",
        "Delete": "删除冗余",
        "Simplify": "简化优化",
        "Accelerate": "加快流程",
        "Automate": "自动化",
        "Pending": "尚未开始",
        "In progress": "进行中",
        "Completed": "已完成",
        "Skipped": "已跳过",
        "Blocked": "暂时受阻",
        "Waiting for your prompt": "等待你的指令",
        "No report yet": "暂无进度记录",
        "This step is ready. Ask the agent to begin; it will guide you through the work and update this indicator.": "此步骤已就绪。请发出开始指令，助手将引导你完成工作并更新进度。",
        "This step hasn't started yet.": "此步骤尚未开始。",
        "Challenge requirements and define the outcome.": "审视需求，明确真正要达成的目标。",
        "Remove unnecessary parts or steps.": "删除不必要的部分或步骤。",
        "Make what remains simpler and easier to use.": "让保留的部分更简单、更容易使用。",
        "Shorten the bottleneck that limits progress.": "缩短限制整体进度的瓶颈环节。",
        "Repeat a verified workflow with less manual work.": "将已验证的流程自动化，减少手动操作。",
        "Title tracking has not started.": "标题跟随尚未启用。",
        "Preview mode: tracking other apps is disabled.": "预览模式：不会读取其他应用。",
        "Title tracking enabled. Return to Codex to attach the progress bar.": "标题跟随已启用。返回 Codex 后，进度条将附着在标题旁。",
        "Allow Five Step HUD in macOS Accessibility, then return to Codex.": "请在 macOS 辅助功能中允许 Five Step HUD，然后返回 Codex。",
        "Host window unavailable. Progress remains in the menu bar.": "暂时无法定位应用窗口，进度显示在菜单栏中。",
        "Choose Enable Title Tracking to attach beside the task title.": "点击“启用标题跟随”，让进度条附着在任务标题旁。",
        "Task title button unavailable. Progress remains in the menu bar.": "暂时无法定位任务标题按钮，进度显示在菜单栏中。",
        "Attached beside the task title. Position is locked.": "已附着在任务标题旁，位置已锁定。",
        "Attached beside the task title. Position is unlocked.": "已附着在任务标题旁，位置已解锁。",
        "Not enough space beside the title. Progress remains in the menu bar.": "标题旁的空间不足，进度显示在菜单栏中。",
        "Update unavailable": "暂时无法更新",
        "Open a Five Step session file": "请打开一个五步进度会话文件",
        "Selected session is not a regular file": "所选会话不是普通文件",
        "Session exceeds 64 KiB": "会话文件超过 64 KiB",
        "Malformed session JSON": "会话 JSON 格式不正确",
        "Unsupported schema version": "不支持此会话格式版本",
        "Revision must be positive": "修订号必须为正数",
        "Session is outside the expected project state directory": "会话不在预期的项目状态目录中",
        "Project path must be absolute": "项目路径必须为绝对路径",
        "Project path does not match the selected session": "项目路径与所选会话不匹配",
        "Task ID does not match the session filename": "任务标识与会话文件名不匹配",
        "Stages must use the fixed five-stage order": "必须按固定顺序排列五个阶段",
        "Pending stages cannot contain report details": "尚未开始的阶段不能含有进度说明",
        "Reported stages require a reason of at most 300 characters": "已报告的阶段必须含有不超过 300 字符的说明",
        "Reported stages require a timestamp": "已报告的阶段必须含有时间戳",
        "A stage cannot begin before earlier stages are completed or skipped": "前面的阶段完成或跳过后才能开始下一阶段",
        "Only one stage may be active or blocked": "只能有一个进行中或受阻的阶段",
        "The active or blocked stage must be current": "进行中或受阻的阶段必须是当前阶段",
        "An untouched session cannot have a current stage": "尚无进度记录的会话不能指定当前阶段",
        "Current stage must identify the latest explicit report": "当前阶段必须对应最近一次明确的进度记录",
        "Invalid task ID": "任务标识无效",
        "Invalid title": "标题无效",
        "Invalid session fields": "会话字段无效",
        "Invalid stage fields": "阶段字段无效",
        "Invalid updatedAt": "更新时间无效",
        "Invalid stage updatedAt": "阶段更新时间无效",
        "updatedAt must be a UTC timestamp with milliseconds": "更新时间必须是包含毫秒的 UTC 时间戳",
        "stage updatedAt must be a UTC timestamp with milliseconds": "阶段更新时间必须是包含毫秒的 UTC 时间戳",
        "Preview only. No host app is inspected.": "仅供预览，不会读取其他应用。",
        "This preview never accesses another app.": "此预览不会读取其他应用。",
    ]
}
