import CryptoKit
import Foundation
import SQLite3

// Read only task identity metadata. Never inspect rollout files or message text.
// The desktop uses an in-memory router, so its document URL is not a reliable
// indication of the visible task. A full, unique header name resolves to an ID;
// missing/duplicate names or an unsupported index must hide progress.
struct CodexTaskIndex {
    let databaseURL: URL?

    init(databaseURL: URL? = Self.defaultDatabaseURL) { self.databaseURL = databaseURL }

    private static var defaultDatabaseURL: URL? {
        let folder = ProcessInfo.processInfo.environment["CODEX_HOME"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex")
        return (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil))?
            .filter { $0.lastPathComponent.range(of: #"^state_[0-9]+\.sqlite$"#, options: .regularExpression) != nil }
            .sorted { $0.lastPathComponent.compare($1.lastPathComponent, options: .numeric) == .orderedDescending }
            .first
    }

    func taskID(forTitle title: String) -> String? {
        guard !title.isEmpty, let databaseURL else { return nil }
        var database: OpaquePointer?
        guard sqlite3_open_v2(databaseURL.path, &database, SQLITE_OPEN_READONLY | SQLITE_OPEN_NOMUTEX, nil) == SQLITE_OK else {
            sqlite3_close(database)
            return nil
        }
        defer { sqlite3_close(database) }
        sqlite3_busy_timeout(database, 15)
        var statement: OpaquePointer?
        let query = "SELECT id FROM threads WHERE COALESCE(NULLIF(name, ''), title) = ? COLLATE BINARY LIMIT 2"
        guard sqlite3_prepare_v2(database, query, -1, &statement, nil) == SQLITE_OK else { return nil }
        defer { sqlite3_finalize(statement) }
        guard sqlite3_bind_text(statement, 1, title, -1, unsafeBitCast(-1, to: sqlite3_destructor_type.self)) == SQLITE_OK,
              sqlite3_step(statement) == SQLITE_ROW, let bytes = sqlite3_column_text(statement, 0) else { return nil }
        let taskID = String(cString: bytes)
        guard !taskID.isEmpty, sqlite3_step(statement) == SQLITE_DONE else { return nil }
        return taskID
    }
}

@MainActor
final class HUDSessions {
    private let store: ProgressStateStore
    private let defaults: UserDefaults
    private var paths: Set<String>
    private static let key = "FiveStepHUD.registeredSessions"

    init(store: ProgressStateStore, defaults: UserDefaults = .standard) {
        self.store = store
        self.defaults = defaults
        paths = Set(defaults.stringArray(forKey: Self.key) ?? [])
        if let legacy = defaults.string(forKey: "FiveStepHUD.lastSessionPath"),
           (try? ProgressState.load(from: URL(fileURLWithPath: legacy))) != nil {
            paths.insert(URL(fileURLWithPath: legacy).standardizedFileURL.resolvingSymlinksInPath().path)
        }
    }

    func register(_ url: URL) throws {
        let normalized = url.standardizedFileURL.resolvingSymlinksInPath()
        _ = try ProgressState.load(from: normalized)
        paths.insert(normalized.path)
        defaults.set(paths.sorted(), forKey: Self.key)
    }

    func select(taskID: String?) {
        guard let taskID else { store.clear(); return }
        let digest = SHA256.hash(data: Data(taskID.utf8)).map { String(format: "%02x", $0) }.joined() + ".json"
        let matches = paths.filter {
            URL(fileURLWithPath: $0).lastPathComponent == digest && !Self.definitelyMissing($0)
        }
        guard matches.count == 1, let selected = matches.first else { store.clear(); return }
        store.bind(to: URL(fileURLWithPath: selected))
        if store.errorMessage != nil || store.snapshot?.taskId != taskID { store.clear() }
    }

    private static func definitelyMissing(_ path: String) -> Bool {
        do {
            _ = try FileManager.default.attributesOfItem(atPath: path)
            return false
        } catch let error as NSError {
            // Keep inaccessible or corrupt registrations ambiguous. Missing
            // paths stay registered too, so a returning file is re-evaluated.
            return error.domain == NSCocoaErrorDomain &&
                [NSFileNoSuchFileError, NSFileReadNoSuchFileError].contains(error.code)
        }
    }
}
