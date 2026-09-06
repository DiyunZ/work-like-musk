import AppKit
import CryptoKit
import SQLite3

@main
struct HUDSessionTests {
    @MainActor
    static func main() throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: folder) }
        let database = folder.appendingPathComponent("state_5.sqlite")
        var db: OpaquePointer?
        precondition(sqlite3_open(database.path, &db) == SQLITE_OK)
        defer { sqlite3_close(db) }
        func sql(_ statement: String) {
            precondition(sqlite3_exec(db, statement, nil, nil, nil) == SQLITE_OK)
        }
        sql("CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, name TEXT)")
        sql("INSERT INTO threads VALUES ('task-a', 'Initial message A', 'Task A'), ('task-b', 'Task B', NULL), ('unregistered', 'Other task', '')")
        let index = CodexTaskIndex(databaseURL: database)
        precondition(index.taskID(forTitle: "Task A") == "task-a")
        precondition(index.taskID(forTitle: "Task") == nil, "Never match a title prefix")
        precondition(index.taskID(forTitle: "Missing") == nil)
        precondition(index.taskID(forTitle: "Initial message A") == nil, "Use the displayed name before the original prompt title")
        sql("INSERT INTO threads VALUES ('duplicate', 'Task A', NULL)")
        precondition(index.taskID(forTitle: "Task A") == nil, "Hide ambiguous titles, including unregistered tasks")
        sql("DELETE FROM threads WHERE id='duplicate'")
        sql("UPDATE threads SET name='Renamed B' WHERE id='task-b'")
        precondition(index.taskID(forTitle: "Task B") == nil)
        precondition(index.taskID(forTitle: "Renamed B") == "task-b")
        let suite = "org.worklikemusk.hud.session-tests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = ProgressStateStore()
        let sessions = HUDSessions(store: store, defaults: defaults)
        let a = try fixture(folder: folder.appendingPathComponent("A"), task: "task-a")
        let b = try fixture(folder: folder.appendingPathComponent("B"), task: "task-b")
        try sessions.register(a)
        precondition(store.snapshot == nil, "Registering a background task must not steal the foreground")
        sessions.select(taskID: "task-a")
        precondition(store.snapshot?.taskId == "task-a" && store.snapshot?.waitingStageID == .question)
        try sessions.register(b)
        precondition(store.snapshot?.taskId == "task-a")
        sessions.select(taskID: "task-b")
        precondition(store.snapshot?.taskId == "task-b")
        sessions.select(taskID: "unregistered")
        precondition(store.snapshot == nil && store.boundURL == nil)
        sessions.select(taskID: "task-a")
        precondition(store.snapshot?.taskId == "task-a")
        sessions.select(taskID: nil)
        precondition(store.snapshot == nil)
        let restored = HUDSessions(store: store, defaults: defaults)
        restored.select(taskID: "task-b")
        precondition(store.snapshot?.taskId == "task-b", "Restore all registered sessions after restart")
        let validB = try Data(contentsOf: b)
        try Data("{broken".utf8).write(to: b)
        restored.select(taskID: "task-b")
        precondition(store.snapshot == nil, "A read error must not leave an older report on screen")
        try validB.write(to: b)
        restored.select(taskID: "task-b")
        precondition(store.snapshot?.taskId == "task-b")
        let duplicate = try fixture(folder: folder.appendingPathComponent("duplicate"), task: "task-a")
        try restored.register(duplicate)
        restored.select(taskID: "task-a")
        precondition(store.snapshot == nil, "An ID registered under two projects is ambiguous")
        let savedA = try Data(contentsOf: a)
        try FileManager.default.removeItem(at: a)
        restored.select(taskID: "task-a")
        precondition(store.boundURL == duplicate,
                     "A removed old project session must not block the one remaining registered session")
        let afterMove = HUDSessions(store: store, defaults: defaults)
        afterMove.select(taskID: "task-a")
        precondition(store.boundURL == duplicate, "Recovery from the removed path must survive restart")
        try savedA.write(to: a)
        afterMove.select(taskID: "task-a")
        precondition(store.snapshot == nil,
                     "If the old file returns, both existing registrations are ambiguous again")
        sql("DROP TABLE threads")
        precondition(index.taskID(forTitle: "Task A") == nil)
        print("PASS: exact task lookup, duplicate and renamed titles, background registration, A/B/unregistered switching and restart")
    }

    static func fixture(folder: URL, task: String) throws -> URL {
        let project = folder.standardizedFileURL.resolvingSymlinksInPath()
        let sessions = project.appendingPathComponent(".work-like-musk/sessions")
        try FileManager.default.createDirectory(at: sessions, withIntermediateDirectories: true)
        let digest = SHA256.hash(data: Data(task.utf8)).map { String(format: "%02x", $0) }.joined()
        let url = sessions.appendingPathComponent(digest + ".json")
        let object: [String: Any] = ["schemaVersion": 1, "projectPath": project.path, "taskId": task,
            "title": task, "revision": 1, "updatedAt": "2026-09-06T07:00:00.000Z", "currentStage": NSNull(),
            "stages": ProgressState.StageID.allCases.map {
                ["id": $0.rawValue, "status": "pending", "reason": "", "updatedAt": NSNull()] as [String: Any]
            }]
        try JSONSerialization.data(withJSONObject: object).write(to: url)
        return url
    }
}
