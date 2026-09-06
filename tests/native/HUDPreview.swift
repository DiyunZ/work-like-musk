import AppKit
import SwiftUI

@MainActor
struct HUDPreviewView: View {
    @ObservedObject var store: ProgressStateStore
    @ObservedObject var controls: HUDControls
    @ObservedObject var preferences: HUDPreferences
    let update: (ProgressState.StageID, String, String) -> Void
    @State private var settings = false
    @State private var title = "Improve the project workflow"

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(spacing: 8) {
                TextField("Sample task title", text: $title)
                    .textFieldStyle(.plain).font(.system(size: 14, weight: .semibold))
                    .frame(width: 250)
                Image(systemName: "ellipsis").frame(width: 28, height: 28)
                HUDView(store: store, controls: controls, preferences: preferences)
                Spacer()
            }
            .padding(16)
            .background(Color(nsColor: .windowBackgroundColor))
            HStack(spacing: 16) {
                Text("Menu bar scale").font(.caption).foregroundStyle(.secondary)
                HUDView(store: store, controls: controls, preferences: preferences, isMenuBar: true)
                Spacer()
            }.padding(.horizontal, 20)
            VStack(alignment: .leading, spacing: 15) {
                Text("Design preview · isolated sample session").font(.headline)
                Text("The five symbols stay recognizable. A rotating ring means working; the red breathing dot means waiting for your prompt.")
                    .foregroundStyle(.secondary)
                HStack(spacing: 12) {
                    Button("Start Next Step") {
                        if let id = store.snapshot?.waitingStageID {
                            update(id, "in_progress", "Working on the requested stage in the isolated preview")
                        }
                    }.disabled(store.snapshot?.waitingStageID == nil)
                    Button("Complete Step") {
                        if let stage = activeStage { update(stage.id, "completed", "The preview checkpoint has been verified") }
                    }.disabled(activeStage == nil)
                    Button("Block Step") {
                        if let stage = activeStage { update(stage.id, "blocked", "Waiting for a required decision within this stage") }
                    }.disabled(activeStage == nil)
                    Button("Reopen Question") { update(.question, "in_progress", "Rechecking the preview goal") }
                }
                HStack {
                    Button("Settings…") { controls.dismissDetails(); settings = true }
                    Spacer()
                    Text(store.snapshot?.waitingStageID.map { "\($0.label) is waiting" } ?? "Reported work is active or complete")
                        .font(.caption).foregroundStyle(.secondary)
                }
                if let id = controls.hoveredStage {
                    HUDDetailView(store: store, preferences: preferences, stageID: id)
                }
            }.padding(.horizontal, 20)
            Spacer(minLength: 0)
        }
        .frame(width: 760, height: 520)
        .background(Color(nsColor: .underPageBackgroundColor))
        .preferredColorScheme(preferences.theme == .system ? nil : preferences.theme == .dark ? .dark : .light)
        .sheet(isPresented: $settings) {
            VStack(spacing: 0) {
                HUDSettingsView(preferences: preferences, controls: controls,
                                restorePosition: preferences.restoreDefaultPosition,
                                enableTracking: { controls.placementMessage = "This preview never accesses another app." })
                Button("Done") { settings = false }.padding(12)
            }
        }
        .onAppear {
            controls.onSettings = { controls.dismissDetails(); settings = true }
            controls.onResetPosition = preferences.restoreDefaultPosition
            controls.placementMessage = "Preview only. No host app is inspected."
        }
    }

    private var activeStage: ProgressState.Stage? {
        store.snapshot?.stages.first { $0.status.isActive }
    }
}

@main
struct HUDPreview {
    @MainActor
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 5 else { fatalError("Expected CLI path, project directory, session file and language configuration") }
        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        let store = ProgressStateStore()
        store.bind(to: URL(fileURLWithPath: args[3]))
        let controls = HUDControls()
        let suite = "org.worklikemusk.hud.preview.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let preferences = HUDPreferences(defaults: defaults, configurationURL: URL(fileURLWithPath: args[4]))
        let view = HUDPreviewView(store: store, controls: controls, preferences: preferences) { id, status, reason in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["python3", args[1], "update", "--project", args[2], "--task", "design-preview",
                                 "--expected-revision", String(store.snapshot?.revision ?? 0),
                                 "--stage", id.rawValue, "--status", status, "--reason", reason]
            process.standardOutput = Pipe()
            do { try process.run(); process.waitUntilExit(); store.refresh() }
            catch { controls.placementMessage = error.localizedDescription }
        }
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 520),
                              styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "Five Step Design Preview"
        window.contentView = NSHostingView(rootView: view)
        window.center()
        window.makeKeyAndOrderFront(nil)
        app.activate(ignoringOtherApps: true)
        app.run()
        withExtendedLifetime(window) {}
    }
}
