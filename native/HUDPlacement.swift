import Foundation
import CoreGraphics

struct HUDLayout {
    var isMenuBar = false
    var allowDragging = false
    static let barSize = HUDLayout().size
    static let menuBarSize = HUDLayout(isMenuBar: true).size
    static let detailWidth: CGFloat = 300

    let horizontalPadding: CGFloat = 6
    var stageWidth: CGFloat { isMenuBar ? 22 : 26 }
    var connectorWidth: CGFloat { isMenuBar ? 10 : 16 }
    var settingsGap: CGFloat { isMenuBar ? 12 : 14 }
    var settingsSide: CGFloat { isMenuBar ? 22 : 28 }
    var dragWidth: CGFloat { !isMenuBar && allowDragging ? 34 : 0 }
    var stepsWidth: CGFloat { 5 * stageWidth + 4 * connectorWidth }
    var size: CGSize {
        CGSize(width: 2 * horizontalPadding + dragWidth + stepsWidth + settingsGap + settingsSide,
               height: isMenuBar ? 24 : 30)
    }

    func stageFrame(at index: Int) -> CGRect {
        CGRect(x: horizontalPadding + dragWidth + CGFloat(index) * (stageWidth + connectorWidth),
               y: 0, width: stageWidth, height: size.height)
    }

    var settingsFrame: CGRect {
        CGRect(x: stageFrame(at: 4).maxX + settingsGap, y: (size.height - settingsSide) / 2,
               width: settingsSide, height: settingsSide)
    }
}

enum HUDPlacement {
    // Preserve the exact relationship to the title button; never guess a
    // different position when the adjacent space is occupied or off-screen.
    static func titleBarFrame(anchor: CGRect, host: CGRect, visible: CGRect,
                              obstacles: [CGRect] = [], size: CGSize = HUDLayout.barSize) -> CGRect? {
        let frame = CGRect(x: anchor.maxX + 8, y: anchor.midY - size.height / 2,
                           width: size.width, height: size.height)
        guard host.intersection(visible).contains(frame),
              !obstacles.contains(where: { $0.intersects(frame.insetBy(dx: -4, dy: 0)) }) else { return nil }
        return frame
    }

    // Codex currently uses a 46-point toolbar. Leave room for the sidebar/title
    // and Share controls; a user-calibrated position follows the same window.
    static func barFrame(host: CGRect, visible: CGRect, offset: CGPoint? = nil,
                         size: CGSize = HUDLayout.barSize) -> CGRect? {
        if offset == nil && host.width < 520 + size.width + 132 { return nil }
        let inset = offset ?? CGPoint(x: 132, y: 8)
        let usable = host.intersection(visible)
        guard usable.width >= size.width, usable.height >= size.height else { return nil }
        let proposed = CGPoint(x: host.maxX - inset.x - size.width,
                               y: host.maxY - inset.y - size.height)
        return CGRect(origin: clamped(proposed, size: size, within: usable), size: size)
    }

    static func offset(for frame: CGRect, host: CGRect) -> CGPoint {
        CGPoint(x: host.maxX - frame.maxX, y: host.maxY - frame.maxY)
    }

    static func detailFrame(anchor: CGRect, size: CGSize, visible: CGRect) -> CGRect {
        let below = anchor.minY - 7 - size.height
        let y = below >= visible.minY ? below : anchor.maxY + 7
        return CGRect(origin: clamped(CGPoint(x: anchor.midX - size.width / 2, y: y),
                                      size: size, within: visible), size: size)
    }

    private static func clamped(_ point: CGPoint, size: CGSize, within frame: CGRect) -> CGPoint {
        CGPoint(x: min(max(point.x, frame.minX), frame.maxX - size.width),
                y: min(max(point.y, frame.minY), frame.maxY - size.height))
    }
}
