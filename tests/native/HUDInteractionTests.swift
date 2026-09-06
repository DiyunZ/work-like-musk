import AppKit

@main
struct HUDInteractionTests {
    @MainActor
    static func main() {
        let symbols = ProgressState.StageID.allCases.map(\.symbol)
        precondition(Set(symbols).count == 5 && !symbols.contains("gearshape"))
        precondition(symbols.allSatisfy { NSImage(systemSymbolName: $0, accessibilityDescription: nil) != nil })
        let controls = HUDControls()
        var hovered: ProgressState.StageID?
        controls.onHoverChanged = { hovered = $0 }
        controls.hover(.question, inside: true)
        precondition(hovered == .question)
        controls.hover(.delete, inside: true)
        controls.hover(.question, inside: false)
        precondition(hovered == .delete, "A stale exit must not dismiss the next step")
        controls.hover(.delete, inside: false)
        precondition(hovered == nil)
        controls.hover(.simplify, inside: true)
        controls.beginDrag()
        precondition(controls.isDragging && hovered == nil)
        controls.endDrag()
        precondition(!controls.isDragging)
        let hoverView = NativeHoverView { controls.hover(.automate, inside: $0) }
        hoverView.updateTrackingAreas()
        precondition(hoverView.trackingAreas.count == 1)
        precondition(hoverView.trackingAreas[0].options.contains(.activeAlways),
                     "Hover must work while Codex owns keyboard focus")

        var dragEvents: [String] = []
        let dragView = NativeHeaderDragView(
            onDragStarted: { dragEvents.append("begin") },
            onDragEnded: { dragEvents.append("end") }
        )
        guard let mouseDown = NSEvent.mouseEvent(
            with: .leftMouseDown,
            location: .zero,
            modifierFlags: [],
            timestamp: 0,
            windowNumber: 0,
            context: nil,
            eventNumber: 1,
            clickCount: 1,
            pressure: 1
        ) else {
            fputs("FAIL: could not create drag test event\n", stderr)
            Foundation.exit(1)
        }

        dragView.mouseDown(with: mouseDown)
        hoverView.mouseEntered(with: mouseDown)
        precondition(hovered == .automate)
        hoverView.mouseExited(with: mouseDown)
        precondition(hovered == nil)
        guard dragEvents == ["begin", "end"] else {
            fputs("FAIL: drag lifecycle did not finish\n", stderr)
            Foundation.exit(1)
        }
        print("PASS: hover handoff, dismissal, and native drag lifecycle")
    }
}
