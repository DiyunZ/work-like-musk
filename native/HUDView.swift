import SwiftUI

@MainActor
final class HUDControls: ObservableObject {
    @Published private(set) var hoveredStage: ProgressState.StageID?
    private(set) var isDragging = false
    var onClose: (() -> Void)?
    var onResetPosition: (() -> Void)?
    var onSettings: (() -> Void)?
    var onHoverChanged: ((ProgressState.StageID?) -> Void)?
    var onDragEnded: (() -> Void)?
    @Published var placementMessage = "Title tracking has not started."
    @Published var matchedTaskTitle: String?

    func hover(_ stage: ProgressState.StageID, inside: Bool) {
        if inside {
            hoveredStage = stage
        } else if hoveredStage == stage {
            hoveredStage = nil
        } else {
            return
        }
        onHoverChanged?(hoveredStage)
    }

    func dismissDetails() {
        hoveredStage = nil
        onHoverChanged?(nil)
    }

    func beginDrag() {
        isDragging = true
        dismissDetails()
    }

    func endDrag() {
        isDragging = false
        onDragEnded?()
    }
}

@MainActor
struct HUDView: View {
    @ObservedObject var store: ProgressStateStore
    @ObservedObject var controls: HUDControls
    @ObservedObject var preferences: HUDPreferences
    var isMenuBar = false
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.colorSchemeContrast) private var contrast
    @Environment(\.colorScheme) private var colorScheme

    private var layout: HUDLayout { HUDLayout(isMenuBar: isMenuBar, allowDragging: preferences.allowDragging) }
    private var accent: Color {
        Color(nsColor: preferences.contrastingAccent(on: colorScheme == .dark
            ? NSColor(srgbRed: 0.12, green: 0.12, blue: 0.12, alpha: 1) : .white))
    }
    private var flowingConnector: Int? {
        store.errorMessage == nil ? store.snapshot?.flowingConnectorIndex : nil
    }

    var body: some View {
        HStack(spacing: 0) {
            if !isMenuBar && preferences.allowDragging {
                Image(systemName: store.errorMessage == nil ? "line.3.horizontal" : "exclamationmark.triangle.fill")
                .font(.system(size: 8, weight: .semibold))
                .foregroundStyle(store.errorMessage == nil ? Color.secondary : .red)
                .frame(width: 26, height: 26)
                .overlay {
                    NativeHeaderDragRegion(onDragStarted: controls.beginDrag, onDragEnded: controls.endDrag)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .accessibilityLabel(preferences.text("Move progress bar"))
                .help(preferences.text("Drag to position · Right-click for options"))
                Spacer().frame(width: 8)
            }
            HStack(spacing: layout.connectorWidth) {
                ForEach(ProgressState.StageID.allCases, id: \.self) { id in
                    let stage = store.snapshot?.stages.first { $0.id == id }
                    let status = stage?.status ?? .pending
                    Button {
                        controls.hover(id, inside: true)
                    } label: {
                        StageMark(id: id, status: status, isWaiting: store.snapshot?.waitingStageID == id,
                                  accent: accent, compact: isMenuBar)
                            .frame(width: layout.stageWidth, height: layout.size.height)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(IconButtonStyle())
                    .background(Color.primary.opacity(controls.hoveredStage == id ? 0.05 : 0),
                                in: RoundedRectangle(cornerRadius: 7))
                    .overlay {
                        NativeHoverRegion { controls.hover(id, inside: $0) }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .accessibilityHidden(true)
                    }
                    .accessibilityLabel("\(preferences.text(id.label)), \(preferences.text(store.snapshot?.waitingStageID == id ? "Waiting for your prompt" : status.label))")
                    .accessibilityHint(stage?.reason ?? preferences.text("No report yet"))
                }
            }
            .background {
                FlowConnectors(layout: layout, accent: accent, activeConnector: flowingConnector)
                    .allowsHitTesting(false)
                    .accessibilityHidden(true)
            }
            Spacer().frame(width: layout.settingsGap)
            Button { controls.onSettings?() } label: {
                Image(systemName: store.errorMessage == nil ? "slider.horizontal.3" : "exclamationmark.triangle.fill")
                    .font(.system(size: isMenuBar ? 11 : 13, weight: .medium))
                    .foregroundStyle(store.errorMessage == nil ? Color.primary.opacity(0.8) : .red)
                    .frame(width: layout.settingsSide, height: layout.settingsSide)
                    .background(colorScheme == .dark ? Color(white: 0.22) : Color(white: 0.95),
                                in: RoundedRectangle(cornerRadius: isMenuBar ? 8 : 10, style: .continuous))
                    .contentShape(RoundedRectangle(cornerRadius: 10))
            }
            .buttonStyle(IconButtonStyle())
            .accessibilityLabel(preferences.text("Settings"))
            .help(preferences.text("Settings · Position is \(preferences.allowDragging ? "unlocked" : "locked")"))
        }
        .padding(.horizontal, layout.horizontalPadding)
        .frame(width: layout.size.width, height: layout.size.height)
        .background {
            let shape = RoundedRectangle(cornerRadius: 10, style: .continuous)
            if reduceTransparency || contrast == .increased {
                shape.fill(Color(nsColor: .windowBackgroundColor))
            }
        }
        .overlay {
            if contrast == .increased {
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(Color.primary.opacity(0.5), lineWidth: 0.5)
                    .allowsHitTesting(false)
            }
        }
        .contextMenu {
            Text(store.snapshot?.title ?? preferences.text("Five Step"))
            Button(preferences.text("Settings…")) { controls.onSettings?() }
            Button(preferences.text("Restore Default Position")) { controls.onResetPosition?() }
            Divider()
            Button(preferences.text("Close progress bar")) { controls.onClose?() }
        }
    }
}

private struct FlowConnectors: View {
    let layout: HUDLayout
    let accent: Color
    let activeConnector: Int?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorSchemeContrast) private var contrast
    @State private var visible = false

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30,
                                paused: reduceMotion || !visible || activeConnector == nil)) { timeline in
            Canvas { context, size in
                let centerY = size.height / 2
                let tailLength: CGFloat = 8
                let phase = CGFloat(timeline.date.timeIntervalSinceReferenceDate
                    .truncatingRemainder(dividingBy: 1.2) / 1.2)
                for index in 0..<4 {
                    let start = CGFloat(index) * (layout.stageWidth + layout.connectorWidth) + layout.stageWidth + 2
                    let end = start + layout.connectorWidth - 4
                    var line = Path()
                    line.move(to: CGPoint(x: start, y: centerY))
                    line.addLine(to: CGPoint(x: end, y: centerY))
                    context.stroke(line, with: .color(.primary.opacity(contrast == .increased ? 0.5 : 0.18)),
                                   style: StrokeStyle(lineWidth: 1, lineCap: .round))
                    if index == activeConnector && !reduceMotion {
                        let headX = start - 2 + phase * (end - start + tailLength + 4)
                        var trail = Path()
                        trail.move(to: CGPoint(x: headX - tailLength, y: centerY))
                        trail.addLine(to: CGPoint(x: headX, y: centerY))
                        var clipped = context
                        clipped.clip(to: Path(CGRect(x: start, y: centerY - 3, width: end - start, height: 6)))
                        clipped.stroke(trail, with: .linearGradient(
                            Gradient(colors: [accent.opacity(0), accent.opacity(0.75)]),
                            startPoint: CGPoint(x: headX - tailLength, y: centerY),
                            endPoint: CGPoint(x: headX, y: centerY)),
                            style: StrokeStyle(lineWidth: 2, lineCap: .round))
                        clipped.fill(Path(ellipseIn: CGRect(x: headX - 1.25, y: centerY - 1.25, width: 2.5, height: 2.5)),
                                     with: .color(accent.opacity(0.85)))
                    }
                }
            }
        }
        .onAppear { visible = true }
        .onDisappear { visible = false }
    }
}

@MainActor
struct NativeHoverRegion: NSViewRepresentable {
    var onHover: (Bool) -> Void

    func makeNSView(context: Context) -> NativeHoverView { NativeHoverView(onHover: onHover) }
    func updateNSView(_ view: NativeHoverView, context: Context) { view.onHover = onHover }
}

@MainActor
final class NativeHoverView: NSView {
    var onHover: (Bool) -> Void
    init(onHover: @escaping (Bool) -> Void) {
        self.onHover = onHover
        super.init(frame: .zero)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func hitTest(_ point: NSPoint) -> NSView? { nil }
    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        for area in trackingAreas { removeTrackingArea(area) }
        addTrackingArea(NSTrackingArea(rect: .zero,
                                      options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                                      owner: self, userInfo: nil))
    }
    override func mouseEntered(with event: NSEvent) { onHover(true) }
    override func mouseExited(with event: NSEvent) { onHover(false) }
}

struct StageMark: View {
    let id: ProgressState.StageID
    let status: ProgressState.Status
    let isWaiting: Bool
    let accent: Color
    let compact: Bool
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var visible = false

    var body: some View {
        let tint = status == .inProgress ? accent : status.color(in: colorScheme)
        TimelineView(.animation(minimumInterval: 1.0 / 30,
                                paused: reduceMotion || !visible || !(status == .inProgress || isWaiting))) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate
            let breathing = reduceMotion ? 1 : 0.65 + 0.35 * cos(time * .pi)
            ZStack {
                Image(systemName: id.symbol)
                    .font(.system(size: compact ? 11 : 13, weight: .medium))
                    .foregroundStyle(isWaiting ? Color.primary.opacity(0.75) : tint)
                    .opacity(status == .skipped ? 0.55 : 1)
                if status == .inProgress {
                    Circle().stroke(accent.opacity(0.16), lineWidth: 1.5)
                    Circle().trim(from: 0, to: 0.24)
                        .stroke(accent, style: StrokeStyle(lineWidth: 1.6, lineCap: .round))
                        .rotationEffect(.degrees(reduceMotion ? -90 : time.truncatingRemainder(dividingBy: 1.2) / 1.2 * 360))
                }
                if isWaiting {
                    Circle().fill(Color.red.opacity(0.12 * breathing))
                        .frame(width: 11, height: 11)
                        .overlay(Circle().fill(Color.red.opacity(0.45 + 0.45 * breathing)).frame(width: 4, height: 4))
                        .offset(x: 10, y: 10)
                } else if status == .completed {
                    Image(systemName: "checkmark")
                        .font(.system(size: 6, weight: .heavy))
                        .foregroundStyle(tint)
                        .offset(x: 10, y: 10)
                } else if status == .blocked {
                    Image(systemName: "exclamationmark")
                        .font(.system(size: 7, weight: .heavy))
                        .foregroundStyle(tint)
                        .offset(x: 10, y: 10)
                } else if status == .skipped {
                    Text("–").font(.system(size: 8, weight: .semibold))
                        .foregroundStyle(.secondary).offset(x: 10, y: 10)
                }
            }
            .frame(width: compact ? 21 : 25, height: compact ? 21 : 25)
        }
        .onAppear { visible = true }
        .onDisappear { visible = false }
        .accessibilityHidden(true)
    }
}

@MainActor
private struct IconButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(configuration.isPressed ? 0.7 : 1)
            .background(Color.primary.opacity(configuration.isPressed ? 0.08 : 0),
                        in: RoundedRectangle(cornerRadius: 7))
    }
}

// Hosted by a non-key panel so merely hovering cannot take keyboard focus.
struct HUDDetailView: View {
    @ObservedObject var store: ProgressStateStore
    @ObservedObject var preferences: HUDPreferences
    let stageID: ProgressState.StageID
    @Environment(\.colorScheme) private var colorScheme

    private var stage: ProgressState.Stage? {
        store.snapshot?.stages.first { $0.id == stageID }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let snapshot = store.snapshot {
                Text(snapshot.title)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Text(preferences.text(stageID.label)).font(.system(size: 14, weight: .semibold))
                Spacer(minLength: 8)
                let status = stage?.status ?? .pending
                Text(preferences.text(store.snapshot?.waitingStageID == stageID ? "Waiting for your prompt" : status.label))
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(status == .inProgress ? Color.primary
                                      : status.color(in: colorScheme))
            }
            Text(preferences.text(stageID.summary))
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Text(reason)
                .font(.system(size: 12))
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
            if let error = store.errorMessage {
                Label("\(preferences.text("Update unavailable")): \(preferences.text(error))", systemImage: "exclamationmark.triangle.fill")
                    .font(.system(size: 11))
                    .foregroundStyle(ProgressState.Status.blocked.color(in: colorScheme))
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let timestamp = stage?.updatedAt {
                Text(timestamp.formatted(Date.FormatStyle(date: .abbreviated, time: .standard).locale(preferences.language.locale)))
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(width: HUDLayout.detailWidth, alignment: .leading)
        .background(Color(nsColor: .windowBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(Color.primary.opacity(0.12), lineWidth: 0.5)
        }
    }

    private var reason: String {
        if store.snapshot?.waitingStageID == stageID {
            return preferences.text("This step is ready. Ask the agent to begin; it will guide you through the work and update this indicator.")
        }
        guard let stage, !stage.reason.isEmpty else { return preferences.text("This step hasn't started yet.") }
        return stage.reason
    }
}

@MainActor
struct NativeHeaderDragRegion: NSViewRepresentable {
    var onDragStarted: () -> Void
    var onDragEnded: () -> Void

    func makeNSView(context: Context) -> NativeHeaderDragView {
        NativeHeaderDragView(onDragStarted: onDragStarted, onDragEnded: onDragEnded)
    }

    func updateNSView(_ nsView: NativeHeaderDragView, context: Context) {
        nsView.onDragStarted = onDragStarted
        nsView.onDragEnded = onDragEnded
    }
}

@MainActor
final class NativeHeaderDragView: NSView {
    var onDragStarted: () -> Void
    var onDragEnded: () -> Void

    init(onDragStarted: @escaping () -> Void, onDragEnded: @escaping () -> Void) {
        self.onDragStarted = onDragStarted
        self.onDragEnded = onDragEnded
        super.init(frame: .zero)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
    override func resetCursorRects() { addCursorRect(bounds, cursor: .openHand) }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseDown(with event: NSEvent) {
        onDragStarted()
        defer { onDragEnded() }
        guard let window else { return }
        NSCursor.closedHand.push()
        defer { NSCursor.pop() }
        window.performDrag(with: event)
    }
}

extension ProgressState.StageID {
    var summary: String {
        switch self {
        case .question: return "Challenge requirements and define the outcome."
        case .delete: return "Remove unnecessary parts or steps."
        case .simplify: return "Make what remains simpler and easier to use."
        case .accelerate: return "Shorten the bottleneck that limits progress."
        case .automate: return "Repeat a verified workflow with less manual work."
        }
    }

    var symbol: String {
        switch self {
        case .question: return "questionmark.bubble"
        case .delete: return "scissors"
        case .simplify: return "line.3.horizontal.decrease"
        case .accelerate: return "bolt"
        case .automate: return "repeat"
        }
    }
}

private extension ProgressState.Status {
    func color(in scheme: ColorScheme) -> Color {
        switch self {
        case .pending, .skipped: return Color.primary.opacity(0.55)
        case .inProgress:
            return scheme == .dark ? Color(red: 0.50, green: 0.68, blue: 1)
                : Color(red: 0.15, green: 0.36, blue: 0.82)
        case .completed:
            return scheme == .dark ? Color(red: 0.48, green: 0.80, blue: 0.60)
                : Color(red: 0.10, green: 0.43, blue: 0.26)
        case .blocked:
            return scheme == .dark ? Color(red: 1, green: 0.70, blue: 0.34)
                : Color(red: 0.65, green: 0.32, blue: 0.02)
        }
    }
}
