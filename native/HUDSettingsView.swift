import SwiftUI

struct HUDSettingsView: View {
    @ObservedObject var preferences: HUDPreferences
    @ObservedObject var controls: HUDControls
    let restorePosition: () -> Void
    let enableTracking: () -> Void

    var body: some View {
        Form {
            Section {
                if let title = controls.matchedTaskTitle {
                    Text("\(preferences.text("Last verified task")): \(title)").font(.caption)
                }
                Picker(preferences.text("Show Progress In"), selection: $preferences.placement) {
                    ForEach(HUDPreferences.Placement.allCases, id: \.self) { item in
                        Text(preferences.text(item.label)).tag(item)
                    }
                }
                Toggle(preferences.text("Allow Dragging"), isOn: $preferences.allowDragging)
                Text(preferences.text("Off by default. Unlocking lets you drag the left handle; locking restores the title anchor."))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button(preferences.text("Restore Default Position"), action: restorePosition)
                Text(preferences.text(controls.placementMessage)).font(.caption).foregroundStyle(.secondary)
                Button(preferences.text("Enable Title Tracking…"), action: enableTracking)
                Text(preferences.text("Requires macOS Accessibility permission. Reads the task header and toolbar geometry, then checks local task names and IDs; no chat content."))
                    .font(.caption).foregroundStyle(.secondary)
            } header: {
                Text(preferences.text("Position"))
            }
            Section {
                Picker(preferences.text("Appearance"), selection: $preferences.theme) {
                    ForEach(HUDPreferences.Theme.allCases, id: \.self) { item in
                        Text(preferences.text(item.label)).tag(item)
                    }
                }
                ColorPicker(preferences.text("Accent Color"), selection: Binding(
                    get: { Color(nsColor: preferences.accentColor) },
                    set: { preferences.setAccentColor(NSColor($0)) }
                ), supportsOpacity: false)
                HStack(spacing: 10) {
                    ForEach(["#265CD1", "#27845D", "#8253C7", "#C46A22", "#B74566"], id: \.self) { hex in
                        Button {
                            preferences.accentHex = hex
                        } label: {
                            Circle().fill(color(hex))
                                .frame(width: 18, height: 18)
                                .overlay(Circle().strokeBorder(.primary.opacity(preferences.accentHex == hex ? 0.8 : 0), lineWidth: 2))
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel(preferences.text("Use \(colorName(hex)) accent"))
                    }
                    Spacer()
                }
            } header: {
                Text(preferences.text("Appearance"))
            }
            Text(preferences.text("Hover over a step for details. Right-click the progress bar to open settings."))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .formStyle(.grouped)
        .frame(width: 420, height: 540)
    }

    private func color(_ hex: String) -> Color {
        let value = UInt32(hex.dropFirst(), radix: 16) ?? 0
        return Color(red: Double((value >> 16) & 255) / 255,
                     green: Double((value >> 8) & 255) / 255,
                     blue: Double(value & 255) / 255)
    }

    private func colorName(_ hex: String) -> String {
        switch hex {
        case "#27845D": return "green"
        case "#8253C7": return "purple"
        case "#C46A22": return "orange"
        case "#B74566": return "pink"
        default: return "blue"
        }
    }
}
