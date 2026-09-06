import Foundation
import CoreGraphics

@main
struct HUDPlacementTests {
    static func main() {
        let screen = CGRect(x: 0, y: 0, width: 1512, height: 944)
        let host = CGRect(x: 100, y: 80, width: 1200, height: 800)
        let frame = HUDPlacement.barFrame(host: host, visible: screen)!
        precondition(frame.size == CGSize(width: 248, height: 30))
        precondition(frame.maxX == host.maxX - 132)
        precondition(frame.maxY == host.maxY - 8)
        precondition(frame.minX >= host.minX + 520)
        precondition(HUDPlacement.barFrame(host: CGRect(x: 0, y: 0, width: 700, height: 800), visible: screen) == nil)

        let offset = CGPoint(x: 210, y: 12)
        let calibrated = HUDPlacement.barFrame(host: host, visible: screen, offset: offset)!
        let moved = HUDPlacement.barFrame(host: host.offsetBy(dx: 20, dy: -30), visible: screen, offset: offset)!
        precondition(moved == calibrated.offsetBy(dx: 20, dy: -30))
        precondition(HUDPlacement.offset(for: calibrated, host: host) == offset)

        let otherScreen = CGRect(x: -1920, y: -300, width: 1920, height: 1080)
        let otherHost = CGRect(x: -1900, y: -200, width: 1600, height: 900)
        precondition(otherScreen.contains(HUDPlacement.barFrame(host: otherHost, visible: otherScreen)!))
        let tooltip = HUDPlacement.detailFrame(anchor: frame, size: CGSize(width: 300, height: 230), visible: screen)
        precondition(tooltip.maxY == frame.minY - 7)
        precondition(screen.contains(tooltip))
        let nearBottom = CGRect(x: 2, y: 5, width: 30, height: 30)
        let flipped = HUDPlacement.detailFrame(anchor: nearBottom, size: CGSize(width: 300, height: 230), visible: screen)
        precondition(flipped.minY == nearBottom.maxY + 7)
        precondition(screen.contains(flipped))
        let locked = HUDLayout()
        let unlocked = HUDLayout(allowDragging: true)
        for layout in [locked, unlocked, HUDLayout(isMenuBar: true)] {
            let bounds = CGRect(origin: .zero, size: layout.size)
            for index in 0..<5 {
                precondition(bounds.contains(layout.stageFrame(at: index)), "Every hover target must fit its strip")
                if index < 4 {
                    precondition(layout.stageFrame(at: index).maxX < layout.stageFrame(at: index + 1).minX)
                }
            }
            precondition(bounds.contains(layout.settingsFrame), "Trailing settings must never be clipped")
            precondition(layout.settingsFrame.minX - layout.stageFrame(at: 4).maxX >= 12)
        }
        precondition(unlocked.stageFrame(at: 0).minX - locked.stageFrame(at: 0).minX >= 26)
        let nearRight = CGRect(x: host.maxX - locked.size.width - 8 - 28 - 10,
                               y: host.maxY - 38, width: 28, height: 28)
        precondition(HUDPlacement.titleBarFrame(anchor: nearRight, host: host, visible: screen) != nil)
        precondition(HUDPlacement.titleBarFrame(anchor: nearRight, host: host, visible: screen,
                                                size: unlocked.size) == nil,
                     "Unlocked width must participate in the title collision check")
        print("PASS: strip/hover geometry, trailing settings, unlocked bounds, calibrated follow, and tooltip placement")
    }
}
