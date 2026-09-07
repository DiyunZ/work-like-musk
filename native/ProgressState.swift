import Combine
import CryptoKit
import Foundation

struct ProgressState: Equatable {
    enum StageID: String, Codable, CaseIterable {
        case question
        case delete
        case simplify
        case accelerate
        case automate

        var label: String {
            rawValue.prefix(1).uppercased() + rawValue.dropFirst()
        }
    }

    enum Status: String, Codable {
        case pending
        case inProgress = "in_progress"
        case completed
        case skipped
        case blocked

        var label: String {
            switch self {
            case .pending: return "Pending"
            case .inProgress: return "In progress"
            case .completed: return "Completed"
            case .skipped: return "Skipped"
            case .blocked: return "Blocked"
            }
        }

        var isTerminal: Bool {
            self == .completed || self == .skipped
        }

        var isActive: Bool {
            self == .inProgress || self == .blocked
        }
    }

    struct Stage: Codable, Equatable, Identifiable {
        let id: StageID
        let status: Status
        let reason: String
        let updatedAt: Date?
    }

    let schemaVersion: Int
    let projectPath: String
    let taskId: String
    let title: String
    let revision: Int
    let updatedAt: Date
    let currentStage: StageID?
    let stages: [Stage]

    // Readiness is derived from explicit reports; it never starts a stage.
    var waitingStageID: StageID? {
        guard let next = stages.first(where: { !$0.status.isTerminal }),
              next.status == .pending else { return nil }
        return next.id
    }

    var flowingConnectorIndex: Int? {
        guard let next = stages.firstIndex(where: { !$0.status.isTerminal }), next > 0,
              stages[next].status == .pending || stages[next].status == .inProgress else { return nil }
        return next - 1
    }

    static func load(from url: URL) throws -> ProgressState {
        let selectedURL = url.standardizedFileURL.resolvingSymlinksInPath()
        let values: URLResourceValues
        do {
            values = try selectedURL.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
        } catch {
            throw ValidationError.unreadable(error.localizedDescription)
        }
        guard values.isRegularFile == true else {
            throw ValidationError.invalid("Selected session is not a regular file")
        }
        guard let fileSize = values.fileSize, fileSize <= 65_536 else {
            throw ValidationError.invalid("Session exceeds 64 KiB")
        }

        let data: Data
        do {
            data = try Data(contentsOf: selectedURL)
        } catch {
            throw ValidationError.unreadable(error.localizedDescription)
        }
        guard data.count <= 65_536 else {
            throw ValidationError.invalid("Session exceeds 64 KiB")
        }

        try validateFieldSets(in: data)
        let raw: RawState
        do {
            raw = try JSONDecoder().decode(RawState.self, from: data)
        } catch {
            throw ValidationError.invalid("Malformed session JSON")
        }

        return try validate(raw, selectedURL: selectedURL)
    }

    private static func validate(_ raw: RawState, selectedURL: URL) throws -> ProgressState {
        guard raw.schemaVersion == 1 else {
            throw ValidationError.invalid("Unsupported schema version")
        }
        try validateTrimmed(raw.taskId, name: "task ID", maximum: 200)
        try validateTrimmed(raw.title, name: "title", maximum: 120)
        guard raw.revision > 0 else {
            throw ValidationError.invalid("Revision must be positive")
        }

        let sessionDirectory = selectedURL.deletingLastPathComponent()
        let metadataDirectory = sessionDirectory.deletingLastPathComponent()
        let projectDirectory = metadataDirectory.deletingLastPathComponent()
        guard sessionDirectory.lastPathComponent == "sessions",
              metadataDirectory.lastPathComponent == ".work-like-musk" else {
            throw ValidationError.identity("Session is outside the expected project state directory")
        }
        guard raw.projectPath.hasPrefix("/") else {
            throw ValidationError.identity("Project path must be absolute")
        }
        let declaredProject = URL(fileURLWithPath: raw.projectPath, isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        guard raw.projectPath == declaredProject.path,
              declaredProject.path == projectDirectory.path else {
            throw ValidationError.identity("Project path does not match the selected session")
        }

        let expectedDigest = SHA256.hash(data: Data(raw.taskId.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        guard selectedURL.pathExtension == "json",
              selectedURL.deletingPathExtension().lastPathComponent == expectedDigest else {
            throw ValidationError.identity("Task ID does not match the session filename")
        }

        let expectedOrder = StageID.allCases
        guard raw.stages.count == expectedOrder.count,
              raw.stages.map(\.id) == expectedOrder else {
            throw ValidationError.invalid("Stages must use the fixed five-stage order")
        }

        let rootTimestamp = try parseTimestamp(raw.updatedAt, name: "updatedAt")
        var stages: [Stage] = []
        for rawStage in raw.stages {
            let timestamp: Date?
            if rawStage.status == .pending {
                guard rawStage.reason.isEmpty, rawStage.updatedAt == nil else {
                    throw ValidationError.invalid("Pending stages cannot contain report details")
                }
                timestamp = nil
            } else {
                let trimmedReason = rawStage.reason.trimmingCharacters(in: .whitespacesAndNewlines)
                guard rawStage.reason == trimmedReason,
                      !trimmedReason.isEmpty,
                      rawStage.reason.unicodeScalars.count <= 300 else {
                    throw ValidationError.invalid("Reported stages require a reason of at most 300 characters")
                }
                guard let timestampText = rawStage.updatedAt else {
                    throw ValidationError.invalid("Reported stages require a timestamp")
                }
                timestamp = try parseTimestamp(timestampText, name: "stage updatedAt")
            }
            stages.append(Stage(id: rawStage.id, status: rawStage.status, reason: rawStage.reason, updatedAt: timestamp))
        }

        for index in stages.indices where stages[index].status != .pending {
            guard stages[..<index].allSatisfy({ $0.status.isTerminal }) else {
                throw ValidationError.invalid("A stage cannot begin before earlier stages are completed or skipped")
            }
        }

        let activeStages = stages.filter { $0.status.isActive }
        guard activeStages.count <= 1 else {
            throw ValidationError.invalid("Only one stage may be active or blocked")
        }
        if let active = activeStages.first, raw.currentStage != active.id {
            throw ValidationError.invalid("The active or blocked stage must be current")
        }

        let reportedStages = stages.filter { $0.status != .pending }
        if reportedStages.isEmpty {
            guard raw.currentStage == nil else {
                throw ValidationError.invalid("An untouched session cannot have a current stage")
            }
        } else {
            guard let currentID = raw.currentStage,
                  let current = stages.first(where: { $0.id == currentID }),
                  current.status != .pending,
                  current.updatedAt == rootTimestamp else {
                throw ValidationError.invalid("Current stage must identify the latest explicit report")
            }
        }

        return ProgressState(
            schemaVersion: raw.schemaVersion,
            projectPath: declaredProject.path,
            taskId: raw.taskId,
            title: raw.title,
            revision: raw.revision,
            updatedAt: rootTimestamp,
            currentStage: raw.currentStage,
            stages: stages
        )
    }

    private static func validateTrimmed(_ value: String, name: String, maximum: Int) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard value == trimmed, !trimmed.isEmpty, trimmed.unicodeScalars.count <= maximum else {
            throw ValidationError.invalid("Invalid \(name)")
        }
    }

    private static func validateFieldSets(in data: Data) throws {
        let object: Any
        do {
            object = try JSONSerialization.jsonObject(with: data)
        } catch {
            throw ValidationError.invalid("Malformed session JSON")
        }
        let rootKeys: Set<String> = [
            "schemaVersion", "projectPath", "taskId", "title", "revision",
            "updatedAt", "currentStage", "stages"
        ]
        guard let root = object as? [String: Any], Set(root.keys) == rootKeys,
              let stages = root["stages"] as? [Any] else {
            throw ValidationError.invalid("Invalid session fields")
        }
        let stageKeys: Set<String> = ["id", "status", "reason", "updatedAt"]
        guard stages.allSatisfy({ item in
            guard let stage = item as? [String: Any] else { return false }
            return Set(stage.keys) == stageKeys
        }) else {
            throw ValidationError.invalid("Invalid stage fields")
        }
    }

    private static func parseTimestamp(_ value: String, name: String) throws -> Date {
        let pattern = #"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"#
        guard value.range(of: pattern, options: .regularExpression) != nil else {
            throw ValidationError.invalid("\(name) must be a UTC timestamp with milliseconds")
        }
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .iso8601)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"
        formatter.isLenient = false
        guard let date = formatter.date(from: value), formatter.string(from: date) == value else {
            throw ValidationError.invalid("Invalid \(name)")
        }
        return date
    }

    private struct RawState: Codable {
        let schemaVersion: Int
        let projectPath: String
        let taskId: String
        let title: String
        let revision: Int
        let updatedAt: String
        let currentStage: StageID?
        let stages: [RawStage]
    }

    private struct RawStage: Codable {
        let id: StageID
        let status: Status
        let reason: String
        let updatedAt: String?
    }

    enum ValidationError: LocalizedError {
        case unreadable(String)
        case invalid(String)
        case identity(String)

        var errorDescription: String? {
            switch self {
            case .unreadable(let detail): return "Unable to read session: \(detail)"
            case .invalid(let detail): return detail
            case .identity(let detail): return detail
            }
        }
    }
}

@MainActor
final class ProgressStateStore: ObservableObject {
    @Published private(set) var snapshot: ProgressState?
    @Published private(set) var errorMessage: String?
    @Published private(set) var boundURL: URL?

    func clear() {
        if boundURL != nil { boundURL = nil }
        if snapshot != nil { snapshot = nil }
        if errorMessage != nil { errorMessage = nil }
    }

    func bind(to url: URL) {
        let normalized = url.standardizedFileURL.resolvingSymlinksInPath()
        if boundURL != normalized {
            boundURL = normalized
            snapshot = nil
            errorMessage = nil
        }
        refresh()
    }

    func refresh() {
        guard let boundURL else {
            snapshot = nil
            errorMessage = "Open a Five Step session file"
            return
        }
        do {
            snapshot = try ProgressState.load(from: boundURL)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
