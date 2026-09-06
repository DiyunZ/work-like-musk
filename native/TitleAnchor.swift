import AppKit
import ApplicationServices

// Read only the focused window's top toolbar: controls, the task header text and
// geometry. Never read chat content, take screenshots or perform host actions.
enum TitleAnchor {
    private static let buttonRoles = [kAXButtonRole, kAXMenuButtonRole, kAXPopUpButtonRole]
    // threadHeader.moreActions in the installed Codex build, EN / zh-CN / zh-TW.
    private static let actionLabels: Set<String> = ["chat actions", "聊天操作", "對話動作"]

    static func actionLabel(role: String, title: String?, description: String?) -> String? {
        guard buttonRoles.contains(role) else { return nil }
        return [title, description].compactMap { $0 }.first {
            actionLabels.contains($0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
        }
    }
    struct Control: Equatable {
        let label: String
        let frame: CGRect
        let isButton: Bool
    }
    struct Match {
        let button: CGRect
        let obstacles: [CGRect]
        let taskTitle: String?
        let host: CGRect
    }

    static func select(controls: [Control], host: CGRect) -> Match? {
        let topControls = controls.filter {
            $0.frame.width > 0 && $0.frame.height > 0 &&
            $0.frame.midY >= host.maxY - 62 && $0.frame.midY <= host.maxY && host.intersects($0.frame)
        }
        let candidates = topControls.filter {
            $0.isButton && $0.frame.width <= 60 && $0.frame.height <= 50 &&
            actionLabels.contains($0.label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())
        }
        // Ambiguity must hide the overlay instead of covering an unrelated menu.
        guard candidates.count == 1, let anchor = candidates.first else { return nil }
        // The inline rename control exposes the task title as a button. Both
        // buttons and static titles must satisfy the same adjacency checks.
        let titles = Set(topControls.filter {
            !$0.label.isEmpty && $0.frame.maxX <= anchor.frame.minX + 1 &&
            anchor.frame.minX - $0.frame.maxX <= 44 && abs($0.frame.midY - anchor.frame.midY) <= 8
        }.map(\.label))
        return Match(button: anchor.frame, obstacles: topControls.filter {
            $0.frame != anchor.frame && $0.frame.minX >= anchor.frame.maxX
        }.map(\.frame), taskTitle: titles.count == 1 ? titles.first : nil, host: host)
    }

    static var hasPermission: Bool { AXIsProcessTrusted() }

    static func requestPermission() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }

    static func read(processIdentifier: pid_t, screenTop: CGFloat) -> Match? {
        guard hasPermission else { return nil }
        let application = AXUIElementCreateApplication(processIdentifier)
        AXUIElementSetMessagingTimeout(application, 0.12)
        guard let windowValue = attribute(application, kAXFocusedWindowAttribute),
              CFGetTypeID(windowValue) == AXUIElementGetTypeID() else { return nil }
        let window = unsafeBitCast(windowValue, to: AXUIElement.self)
        guard let host = bounds(window, screenTop: screenTop), host.width >= 400, host.height >= 240 else { return nil }
        var controls: [Control] = []
        var visited = 0
        let deadline = Date().addingTimeInterval(0.15)
        let toolbar = CGRect(x: host.minX, y: host.maxY - 70, width: host.width, height: 70)
        func visit(_ element: AXUIElement, depth: Int) {
            guard depth <= 24, visited < 300, Date() < deadline else { return }
            visited += 1
            let role = attribute(element, kAXRoleAttribute) as? String ?? ""
            // Editable fields cannot be title controls. Some host versions wrap
            // their toolbar in a scroll area, so prune those by geometry instead.
            if [kAXTextAreaRole, kAXTextFieldRole].contains(role) { return }
            let frame = bounds(element, screenTop: screenTop)
            if let frame, frame.width > 0, frame.height > 0, !frame.intersects(toolbar) { return }
            if buttonRoles.contains(role) || role == kAXStaticTextRole {
                if let frame, frame.height <= 50 {
                    let title = attribute(element, kAXTitleAttribute) as? String
                    let description = role == kAXStaticTextRole ? nil
                        : attribute(element, kAXDescriptionAttribute) as? String
                    let label = role == kAXStaticTextRole
                        ? (attribute(element, kAXValueAttribute) as? String ?? title ?? "")
                        : actionLabel(role: role, title: title, description: description)
                            ?? [title, description].compactMap { $0 }.first { !$0.isEmpty } ?? ""
                    controls.append(Control(label: label, frame: frame,
                                            isButton: role != kAXStaticTextRole))
                }
                return
            }
            if let children = attribute(element, kAXChildrenAttribute) as? [AXUIElement] {
                for child in children { visit(child, depth: depth + 1) }
            }
        }
        visit(window, depth: 0)
        // Incomplete traversal cannot establish that the anchor is unambiguous.
        guard visited < 300, Date() < deadline else { return nil }
        return select(controls: controls, host: host)
    }

    private static func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
        AXUIElementSetMessagingTimeout(element, 0.03)
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else { return nil }
        return value
    }

    private static func bounds(_ element: AXUIElement, screenTop: CGFloat) -> CGRect? {
        guard let position = attribute(element, kAXPositionAttribute),
              let sizeValue = attribute(element, kAXSizeAttribute),
              CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(sizeValue) == AXValueGetTypeID() else { return nil }
        var point = CGPoint.zero
        var size = CGSize.zero
        guard AXValueGetValue(unsafeBitCast(position, to: AXValue.self), .cgPoint, &point),
              AXValueGetValue(unsafeBitCast(sizeValue, to: AXValue.self), .cgSize, &size),
              [point.x, point.y, size.width, size.height].allSatisfy(\.isFinite) else { return nil }
        return CGRect(x: point.x, y: screenTop - point.y - size.height, width: size.width, height: size.height)
    }
}
