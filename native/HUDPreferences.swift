import AppKit
import Combine

@MainActor
final class HUDPreferences: ObservableObject {
    enum Theme: String, CaseIterable {
        case system, light, dark
        var label: String { rawValue.capitalized }
    }
    enum Placement: String, CaseIterable {
        case titleBar, menuBar, floating
        var label: String {
            switch self {
            case .titleBar: return "Beside Task Title"
            case .menuBar: return "Menu Bar"
            case .floating: return "Floating Bar"
            }
        }
    }
    static let defaultAccent = "#265CD1"
    private let defaults: UserDefaults
    private let configurationURL: URL
    var onChange: (() -> Void)?
    @Published private(set) var language: HUDLanguage

    @Published var theme: Theme {
        didSet { defaults.set(theme.rawValue, forKey: "HUD.theme"); onChange?() }
    }
    @Published var placement: Placement {
        didSet { defaults.set(placement.rawValue, forKey: "HUD.placement"); onChange?() }
    }
    @Published var accentHex: String {
        didSet { defaults.set(accentHex, forKey: "HUD.accentHex"); onChange?() }
    }

    @Published var allowDragging: Bool {
        didSet { defaults.set(allowDragging, forKey: "HUD.allowDragging"); onChange?() }
    }

    init(defaults: UserDefaults = .standard,
         configurationURL: URL = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("hud-config.json")) {
        self.defaults = defaults
        self.configurationURL = configurationURL
        language = HUDLanguage.load(from: configurationURL)
        // Migrate the previous default once, preserving appearance preferences.
        if !defaults.bool(forKey: "HUD.titleBarDefaultV1") {
            defaults.set(Placement.titleBar.rawValue, forKey: "HUD.placement")
            defaults.set(false, forKey: "HUD.allowDragging")
            defaults.removeObject(forKey: "FiveStepHUD.titleBarOffset")
            defaults.set(true, forKey: "HUD.titleBarDefaultV1")
        }
        theme = Theme(rawValue: defaults.string(forKey: "HUD.theme") ?? "") ?? .system
        placement = Placement(rawValue: defaults.string(forKey: "HUD.placement") ?? "") ?? .titleBar
        allowDragging = defaults.bool(forKey: "HUD.allowDragging")
        let stored = defaults.string(forKey: "HUD.accentHex") ?? Self.defaultAccent
        accentHex = Self.isValidHex(stored) ? stored : Self.defaultAccent
    }

    func text(_ english: String) -> String { language.text(english) }

    func refreshLanguage() {
        let updated = HUDLanguage.load(from: configurationURL)
        guard updated != language else { return }
        language = updated
        onChange?()
    }

    var accentColor: NSColor {
        let hex = Self.isValidHex(accentHex) ? accentHex : Self.defaultAccent
        let rgb = UInt32(hex.dropFirst(), radix: 16) ?? 0x265CD1
        return NSColor(srgbRed: Double((rgb >> 16) & 255) / 255,
                       green: Double((rgb >> 8) & 255) / 255,
                       blue: Double(rgb & 255) / 255, alpha: 1)
    }

    func setAccentColor(_ color: NSColor) {
        guard let rgb = color.usingColorSpace(.sRGB) else { return }
        func channel(_ value: CGFloat) -> Int {
            Int((min(max(value, 0), 1) * 255).rounded())
        }
        accentHex = String(format: "#%02X%02X%02X",
                           channel(rgb.redComponent), channel(rgb.greenComponent), channel(rgb.blueComponent))
    }

    // Keep custom accents visible after removing the old filled icon background.
    func contrastingAccent(on background: NSColor) -> NSColor {
        let base = accentColor
        let background = background.usingColorSpace(.sRGB) ?? .white
        func linear(_ value: CGFloat) -> Double {
            let value = Double(value)
            return value <= 0.04045 ? value / 12.92 : pow((value + 0.055) / 1.055, 2.4)
        }
        func luminance(_ color: NSColor) -> Double {
            0.2126 * linear(color.redComponent) + 0.7152 * linear(color.greenComponent)
                + 0.0722 * linear(color.blueComponent)
        }
        let backdrop = luminance(background)
        let endpoint: CGFloat = backdrop > 0.179 ? 0 : 1
        for step in 0...20 {
            let fraction = CGFloat(step) / 20
            let candidate = NSColor(srgbRed: base.redComponent * (1 - fraction) + endpoint * fraction,
                                    green: base.greenComponent * (1 - fraction) + endpoint * fraction,
                                    blue: base.blueComponent * (1 - fraction) + endpoint * fraction, alpha: 1)
            let value = luminance(candidate)
            if (max(value, backdrop) + 0.05) / (min(value, backdrop) + 0.05) >= 3 { return candidate }
        }
        return endpoint == 0 ? .black : .white
    }

    func restoreDefaultPosition() {
        defaults.removeObject(forKey: "FiveStepHUD.titleBarOffset")
        allowDragging = false
        placement = .titleBar
    }

    private static func isValidHex(_ value: String) -> Bool {
        value.range(of: #"^#[0-9A-Fa-f]{6}$"#, options: .regularExpression) != nil
    }
}
