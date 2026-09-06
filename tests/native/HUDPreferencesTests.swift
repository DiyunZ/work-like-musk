import AppKit

@main
struct HUDPreferencesTests {
    @MainActor
    static func main() {
        let suite = "org.worklikemusk.hud.tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let preferences = HUDPreferences(defaults: defaults)
        precondition(preferences.theme == .system && preferences.placement == .titleBar)
        precondition(!preferences.allowDragging)
        preferences.theme = .dark
        preferences.placement = .floating
        preferences.accentHex = "#12AB34"
        preferences.allowDragging = true
        let reopened = HUDPreferences(defaults: defaults)
        precondition(reopened.theme == .dark && reopened.placement == .floating)
        precondition(reopened.accentHex == "#12AB34")
        precondition(reopened.allowDragging)
        reopened.restoreDefaultPosition()
        precondition(reopened.placement == .titleBar && !reopened.allowDragging)
        precondition(reopened.theme == .dark && reopened.accentHex == "#12AB34")
        reopened.accentHex = "#FFFFFF"
        precondition(reopened.contrastingAccent(on: .white).redComponent < 0.59)
        reopened.accentHex = "#000000"
        precondition(reopened.contrastingAccent(on: NSColor(srgbRed: 0.12, green: 0.12, blue: 0.12, alpha: 1)).redComponent > 0.41)
        reopened.accentHex = HUDPreferences.defaultAccent
        precondition(reopened.contrastingAccent(on: .white) == reopened.accentColor)
        defaults.set("invalid", forKey: "HUD.theme")
        defaults.set("bad color", forKey: "HUD.accentHex")
        let repaired = HUDPreferences(defaults: defaults)
        precondition(repaired.theme == .system)
        precondition(repaired.accentHex == HUDPreferences.defaultAccent)
        print("PASS: appearance persistence, invalid preference recovery, and position-only reset")
    }
}
