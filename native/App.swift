import AppKit
import CoreGraphics
import SwiftUI

private let allowedHostBundleIDs: Set<String> = ["com.openai.codex", "com.openai.chat"]

@MainActor
private final class HUDPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

@MainActor
private final class HUDController: NSObject {
    private static let positionKey = "FiveStepHUD.titleBarOffset"
    private let store = ProgressStateStore()
    private lazy var sessions = HUDSessions(store: store)
    private let taskIndex = CodexTaskIndex()
    private let controls = HUDControls()
    private let preferences = HUDPreferences()
    private let panel: HUDPanel
    private let detailPanel: HUDPanel
    private var statusItem: NSStatusItem?
    private var settingsWindow: NSWindow?
    private var detailView: NSHostingView<HUDDetailView>?
    private var pollTimer: Timer?
    private var hostFrame: NSRect?
    private var calibratedOffset: NSPoint?
    // Preview mode exercises our own interface without inspecting another app.
    private let previewMode = CommandLine.arguments.contains("--preview")
    private var stripLayout: HUDLayout { HUDLayout(allowDragging: preferences.allowDragging) }

    override init() {
        panel = Self.makePanel(size: HUDLayout.barSize, title: "Five Step progress")
        detailPanel = Self.makePanel(size: NSSize(width: HUDLayout.detailWidth, height: 150), title: "Step details")
        super.init()
        if let values = UserDefaults.standard.array(forKey: Self.positionKey) as? [Double],
           values.count == 2, values.allSatisfy({ $0.isFinite }) {
            calibratedOffset = NSPoint(x: values[0], y: values[1])
        }
        panel.contentView = NSHostingView(rootView: HUDView(store: store, controls: controls, preferences: preferences))
        detailPanel.ignoresMouseEvents = true
        detailPanel.hasShadow = true
        detailPanel.level = .popUpMenu
        controls.onClose = { NSApplication.shared.terminate(nil) }
        controls.onHoverChanged = { [weak self] stage in self?.showDetails(for: stage) }
        controls.onDragEnded = { [weak self] in self?.savePosition() }
        controls.onSettings = { [weak self] in self?.showSettings() }
        controls.onResetPosition = { [weak self] in self?.restorePosition() }
        preferences.onChange = { [weak self] in self?.applyPreferences() }
        if let screen = NSScreen.main ?? NSScreen.screens.first {
            panel.setFrameOrigin(NSPoint(x: screen.visibleFrame.midX - HUDLayout.barSize.width / 2,
                                         y: screen.visibleFrame.maxY - 38))
        }
        createStatusItem()
        applyPreferences()
        pollTimer = Timer.scheduledTimer(timeInterval: 0.35, target: self,
                                         selector: #selector(poll), userInfo: nil, repeats: true)
    }

    deinit { pollTimer?.invalidate() }

    private static func makePanel(size: NSSize, title: String) -> HUDPanel {
        let panel = HUDPanel(contentRect: NSRect(origin: .zero, size: size),
                             styleMask: [.borderless, .nonactivatingPanel],
                             backing: .buffered, defer: false)
        panel.title = title
        panel.level = .floating
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = false
        panel.animationBehavior = .none
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        return panel
    }

    private func createStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: HUDLayout.menuBarSize.width)
        statusItem = item
        guard let button = item.button else { return }
        button.title = ""
        let view = NSHostingView(rootView: HUDView(store: store, controls: controls,
                                                  preferences: preferences, isMenuBar: true))
        view.frame = button.bounds
        view.autoresizingMask = [.width, .height]
        button.addSubview(view)
    }

    private func applyPreferences() {
        panel.title = preferences.text("Five Step progress")
        detailPanel.title = preferences.text("Step details")
        settingsWindow?.title = preferences.text("Five Step Settings")
        panel.isMovable = preferences.allowDragging
        if panel.frame.size != stripLayout.size { panel.setContentSize(stripLayout.size) }
        switch preferences.theme {
        case .system: NSApplication.shared.appearance = nil
        case .light: NSApplication.shared.appearance = NSAppearance(named: .aqua)
        case .dark: NSApplication.shared.appearance = NSAppearance(named: .darkAqua)
        }
        controls.dismissDetails()
        if !preferences.allowDragging { calibratedOffset = nil }
        updateVisibility()
    }

    func showSettings() {
        controls.dismissDetails()
        // Verify the focused task before Settings intentionally takes focus.
        updateVisibility()
        if settingsWindow == nil {
            let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 540),
                                  styleMask: [.titled, .closable], backing: .buffered, defer: false)
            window.title = preferences.text("Five Step Settings")
            window.isReleasedWhenClosed = false
            window.contentView = NSHostingView(rootView: HUDSettingsView(preferences: preferences,
                controls: controls,
                restorePosition: { [weak self] in self?.restorePosition() },
                enableTracking: { [weak self] in self?.enableTitleTracking() }))
            window.center()
            settingsWindow = window
        }
        settingsWindow?.makeKeyAndOrderFront(nil)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    private func enableTitleTracking() {
        guard !previewMode else {
            controls.placementMessage = "Preview mode: tracking other apps is disabled."
            return
        }
        UserDefaults.standard.set(true, forKey: "HUD.titleTrackingEnabled")
        TitleAnchor.requestPermission()
        controls.placementMessage = TitleAnchor.hasPermission
            ? "Title tracking enabled. Return to Codex to attach the progress bar."
            : "Allow Five Step HUD in macOS Accessibility, then return to Codex."
        updateVisibility()
    }

    private func restorePosition() {
        calibratedOffset = nil
        preferences.restoreDefaultPosition()
        if let statusItem { NSStatusBar.system.removeStatusItem(statusItem) }
        createStatusItem()
        applyPreferences()
    }

    func bind(to url: URL) {
        if previewMode {
            store.bind(to: url)
        } else {
            do { try sessions.register(url) }
            catch { controls.placementMessage = error.localizedDescription }
        }
        updateVisibility()
        if !previewMode && !TitleAnchor.hasPermission { showSettings() }
    }

    func showWaitingState() { updateVisibility() }

    @objc private func poll() {
        preferences.refreshLanguage()
        if previewMode && store.boundURL != nil { store.refresh() }
        updateVisibility()
        if detailPanel.isVisible { positionDetails() }
    }

    private func hideFloatingBar() {
        controls.dismissDetails()
        panel.orderOut(nil)
    }

    private func updateVisibility() {
        if previewMode {
            statusItem?.isVisible = false
            controls.placementMessage = "Preview mode: tracking other apps is disabled."
            if !panel.isVisible { panel.orderFrontRegardless() }
            return
        }
        guard let frontmost = NSWorkspace.shared.frontmostApplication,
              let bundleID = frontmost.bundleIdentifier else {
            hideUnmatchedTask("No verified Five Step task is visible. Progress is hidden.")
            return
        }
        if bundleID == Bundle.main.bundleIdentifier {
            // Settings is not a verified Codex foreground. Retain only its
            // labelled context, refresh that report, and suspend the overlay.
            hideFloatingBar()
            statusItem?.isVisible = false
            if let taskID = store.snapshot?.taskId {
                sessions.select(taskID: taskID)
                if store.snapshot == nil {
                    controls.matchedTaskTitle = nil
                    controls.placementMessage = "This task has no readable Five Step session. Progress is hidden."
                } else {
                    controls.placementMessage = "Return to Codex to verify its current task and show progress."
                }
            }
            return
        }
        if allowedHostBundleIDs.contains(bundleID) {
            guard TitleAnchor.hasPermission else {
                hideUnmatchedTask("Allow Five Step HUD in macOS Accessibility to identify the current task. Progress is hidden.")
                return
            }
            guard let match = TitleAnchor.read(processIdentifier: frontmost.processIdentifier,
                                               screenTop: NSScreen.screens.first?.frame.maxY ?? 0),
                  let title = match.taskTitle, let taskID = taskIndex.taskID(forTitle: title) else {
                hideUnmatchedTask("The current task cannot be identified uniquely. Progress is hidden.")
                return
            }
            let previousTask = store.snapshot?.taskId
            sessions.select(taskID: taskID)
            if previousTask != store.snapshot?.taskId { controls.dismissDetails() }
            guard store.snapshot?.taskId == taskID, store.errorMessage == nil else {
                hideUnmatchedTask("This task has no readable Five Step session. Progress is hidden.")
                return
            }
            if controls.matchedTaskTitle != title { controls.matchedTaskTitle = title }
            let frame = match.host
            hostFrame = frame
            if preferences.placement == .menuBar {
                controls.placementMessage = "Showing progress for the verified current task."
                statusItem?.isVisible = true
                panel.orderOut(nil)
                return
            }
            if !controls.isDragging {
                guard let visible = bestScreen(for: frame)?.visibleFrame else { hideFloatingBar(); return }
                let target: CGRect?
                if preferences.placement == .titleBar && !(preferences.allowDragging && calibratedOffset != nil) {
                    guard UserDefaults.standard.bool(forKey: "HUD.titleTrackingEnabled") else {
                        titleTrackingUnavailable("Choose Enable Title Tracking to attach beside the task title.")
                        return
                    }
                    target = HUDPlacement.titleBarFrame(anchor: match.button, host: frame, visible: visible,
                                                        obstacles: match.obstacles, size: stripLayout.size)
                    let message = "Attached beside the task title. Position is \(preferences.allowDragging ? "unlocked" : "locked")."
                    if controls.placementMessage != message { controls.placementMessage = message }
                } else {
                    target = HUDPlacement.barFrame(host: frame, visible: visible, offset: calibratedOffset,
                                                   size: stripLayout.size)
                }
                guard let target else {
                    titleTrackingUnavailable("Not enough space beside the title. Progress remains in the menu bar.")
                    return
                }
                if panel.frame != target { panel.setFrame(target, display: true) }
            }
        } else {
            hideUnmatchedTask("No verified Five Step task is visible. Progress is hidden.")
            return
        }
        if statusItem?.isVisible == true {
            controls.dismissDetails()
            statusItem?.isVisible = false
        }
        if !panel.isVisible { panel.orderFrontRegardless() }
    }

    private func hideUnmatchedTask(_ message: String) {
        sessions.select(taskID: nil)
        controls.matchedTaskTitle = nil
        statusItem?.isVisible = false
        hideFloatingBar()
        if controls.placementMessage != message { controls.placementMessage = message }
    }

    private func titleTrackingUnavailable(_ message: String) {
        if controls.placementMessage != message { controls.placementMessage = message }
        if panel.isVisible { hideFloatingBar() }
        statusItem?.isVisible = true
    }

    private func savePosition() {
        guard preferences.allowDragging, let hostFrame else { return }
        let offset = HUDPlacement.offset(for: panel.frame, host: hostFrame)
        calibratedOffset = offset
        UserDefaults.standard.set([Double(offset.x), Double(offset.y)], forKey: Self.positionKey)
    }

    private func showDetails(for stage: ProgressState.StageID?) {
        guard let stage, statusItem?.isVisible == true || panel.isVisible else {
            detailPanel.orderOut(nil)
            detailView = nil
            return
        }
        let view = NSHostingView(rootView: HUDDetailView(store: store, preferences: preferences, stageID: stage))
        detailView = view
        detailPanel.contentView = view
        positionDetails()
        if !detailPanel.isVisible { detailPanel.orderFrontRegardless() }
    }

    private func positionDetails() {
        guard let stage = controls.hoveredStage, let detailView,
              let index = ProgressState.StageID.allCases.firstIndex(of: stage) else { return }
        let anchor: NSRect
        if statusItem?.isVisible == true {
            guard let button = statusItem?.button, let window = button.window else { return }
            let rect = HUDLayout(isMenuBar: true).stageFrame(at: index)
            anchor = window.convertToScreen(button.convert(rect, to: nil))
        } else {
            anchor = stripLayout.stageFrame(at: index).offsetBy(dx: panel.frame.minX, dy: panel.frame.minY)
        }
        guard let screen = bestScreen(for: anchor) else { return }
        detailView.layoutSubtreeIfNeeded()
        let size = NSSize(width: HUDLayout.detailWidth, height: ceil(detailView.fittingSize.height))
        let frame = HUDPlacement.detailFrame(anchor: anchor, size: size, visible: screen.visibleFrame)
        if detailPanel.frame != frame { detailPanel.setFrame(frame, display: true) }
    }

    private func bestScreen(for frame: NSRect) -> NSScreen? {
        NSScreen.screens.max { lhs, rhs in
            area(lhs.frame.intersection(frame)) < area(rhs.frame.intersection(frame))
        }
    }

    private func area(_ frame: NSRect) -> CGFloat {
        frame.isNull ? 0 : frame.width * frame.height
    }
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate {
    private static let lastSessionKey = "FiveStepHUD.lastSessionPath"
    private var controller: HUDController?
    private var pendingSessionURLs: [URL] = []

    func applicationDidFinishLaunching(_ notification: Notification) {
        let controller = HUDController()
        self.controller = controller

        if !pendingSessionURLs.isEmpty {
            for url in pendingSessionURLs { bind(to: url) }
            pendingSessionURLs.removeAll()
        } else if let savedPath = UserDefaults.standard.string(forKey: Self.lastSessionKey) {
            bind(to: URL(fileURLWithPath: savedPath))
        } else {
            controller.showWaitingState()
        }
        if CommandLine.arguments.contains("--settings") { controller.showSettings() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        controller?.showSettings()
        return true
    }

    func application(_ application: NSApplication, open urls: [URL]) {
        for url in urls { receive(url) }
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        guard !filenames.isEmpty else {
            sender.reply(toOpenOrPrint: .failure)
            return
        }
        for filename in filenames { receive(URL(fileURLWithPath: filename)) }
        sender.reply(toOpenOrPrint: .success)
    }

    private func receive(_ url: URL) {
        let normalized = url.standardizedFileURL.resolvingSymlinksInPath()
        if controller == nil {
            pendingSessionURLs.append(normalized)
        } else {
            bind(to: normalized)
        }
    }

    private func bind(to url: URL) {
        UserDefaults.standard.set(url.path, forKey: Self.lastSessionKey)
        controller?.bind(to: url)
    }
}

@main
private struct FiveStepHUDMain {
    @MainActor
    static func main() {
        let application = NSApplication.shared
        let delegate = AppDelegate()
        application.delegate = delegate
        application.setActivationPolicy(.accessory)
        application.run()
        withExtendedLifetime(delegate) {}
    }
}
