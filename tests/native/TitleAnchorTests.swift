import AppKit

@main
struct TitleAnchorTests {
    static func main() {
        precondition(TitleAnchor.actionLabel(role: "AXPopUpButton", title: "Chat actions", description: "") == "Chat actions")
        precondition(TitleAnchor.actionLabel(role: "AXMenuButton", title: "", description: "聊天操作") == "聊天操作")
        precondition(TitleAnchor.actionLabel(role: "AXButton", title: "Chat actions", description: "Open menu") == "Chat actions")
        precondition(TitleAnchor.actionLabel(role: "AXTextField", title: "Chat actions", description: nil) == nil)
        let host = CGRect(x: 100, y: 80, width: 1200, height: 800)
        let button = CGRect(x: 560, y: 842, width: 28, height: 28)
        let share = CGRect(x: 1180, y: 842, width: 75, height: 28)
        let controls = [TitleAnchor.Control(label: "Chat actions", frame: button, isButton: true),
                        TitleAnchor.Control(label: "Share", frame: share, isButton: true)]
        let match = TitleAnchor.select(controls: controls, host: host)!
        let title = CGRect(x: 280, y: 845, width: 264, height: 22)
        precondition(TitleAnchor.select(controls: controls + [.init(label: "Task A", frame: title, isButton: false)],
                                       host: host)?.taskTitle == "Task A")
        // Codex renders an editable task title as a button, not static text.
        precondition(TitleAnchor.select(controls: controls + [.init(label: "Task A", frame: title, isButton: true)],
                                       host: host)?.taskTitle == "Task A")
        precondition(TitleAnchor.select(controls: controls, host: host)?.taskTitle == nil)
        precondition(TitleAnchor.select(controls: controls + [.init(label: "Task A", frame: title, isButton: false),
                                                               .init(label: "Task B", frame: title, isButton: false)],
                                       host: host)?.taskTitle == nil)
        let bar = HUDPlacement.titleBarFrame(anchor: match.button, host: host, visible: host,
                                             obstacles: match.obstacles)!
        precondition(bar.minX == button.maxX + 8 && bar.midY == button.midY)
        let shift = CGPoint(x: -1200, y: 180)
        let movedHost = host.offsetBy(dx: shift.x, dy: shift.y)
        let movedAnchor = button.offsetBy(dx: shift.x, dy: shift.y)
        precondition(HUDPlacement.titleBarFrame(anchor: movedAnchor, host: movedHost, visible: movedHost) ==
                     bar.offsetBy(dx: shift.x, dy: shift.y))
        let longerTitle = button.offsetBy(dx: 150, dy: 0)
        precondition(HUDPlacement.titleBarFrame(anchor: longerTitle, host: host, visible: host)?.minX == bar.minX + 150)
        precondition(HUDPlacement.titleBarFrame(anchor: button, host: host, visible: host,
                                                obstacles: [bar]) == nil)
        precondition(HUDPlacement.titleBarFrame(anchor: button.offsetBy(dx: 600, dy: 0), host: host, visible: host) == nil)
        for label in ["聊天操作", "對話動作"] {
            precondition(TitleAnchor.select(controls: [.init(label: label, frame: button, isButton: true)], host: host) != nil)
        }
        precondition(TitleAnchor.select(controls: [.init(label: "Chat actions", frame: CGRect(x: 120, y: 842, width: 28, height: 28), isButton: true)], host: host) != nil)
        precondition(TitleAnchor.select(controls: controls + [.init(label: "Chat actions", frame: button.offsetBy(dx: 200, dy: 0), isButton: true)], host: host) == nil)
        precondition(TitleAnchor.select(controls: [.init(label: "Chat actions", frame: button.offsetBy(dx: 0, dy: -180), isButton: true)], host: host) == nil)
        precondition(TitleAnchor.select(controls: [.init(label: "More actions", frame: button, isButton: true)], host: host) == nil)
        print("PASS: exact title anchor, title/window movement, localized labels, collisions and ambiguity")
    }
}
