import AppKit

@main
struct HUDLanguageTests {
    @MainActor
    static func main() throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: folder) }
        let config = folder.appendingPathComponent("hud-config.json")
        precondition(HUDLanguage.load(from: config) == .english)
        try Data(#"{"language":"zh-CN"}"#.utf8).write(to: config)
        let suite = "org.worklikemusk.hud.language-tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let preferences = HUDPreferences(defaults: defaults, configurationURL: config)
        precondition(preferences.language == .chinese)
        precondition(preferences.text("Settings") == "设置")
        precondition(preferences.text("Waiting for your prompt") == "等待你的指令")
        for label in ["Question", "Delete", "Simplify", "Accelerate", "Automate",
                      "Pending", "In progress", "Completed", "Skipped", "Blocked",
                      "Five Step Settings", "Allow Dragging", "Enable Title Tracking…",
                      "Attached beside the task title. Position is locked."] {
            precondition(preferences.text(label) != label, "Missing Chinese UI text: \(label)")
        }
        preferences.theme = .dark
        preferences.accentHex = "#12AB34"
        preferences.restoreDefaultPosition()
        precondition(preferences.language == .chinese)
        precondition(HUDLanguage.load(from: config) == .chinese)
        try Data(#"{"language":"en"}"#.utf8).write(to: config)
        preferences.refreshLanguage()
        precondition(preferences.language == .english && preferences.text("Settings") == "Settings")
        precondition(preferences.theme == .dark && preferences.accentHex == "#12AB34")
        precondition(HUDPreferences(defaults: defaults, configurationURL: config).language == .english)
        for invalid in [#"{"language":"fr"}"#, #"{"language":null}"#, #"{"language":"zh-CN","unknown":true}"#, "broken"] {
            try Data(invalid.utf8).write(to: config)
            precondition(HUDLanguage.load(from: config) == .english)
            let retained = try String(contentsOf: config, encoding: .utf8)
            precondition(retained == invalid)
        }
        for (key, translated) in HUDLanguage.translations {
            precondition(!translated.isEmpty && HUDLanguage.english.text(key) == key)
        }
        print("PASS: English/Chinese labels, saved language, live refresh, position-only reset and invalid-config fallback")
    }
}
