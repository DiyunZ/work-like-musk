import Foundation

@main
struct ProgressStateTests {
    private struct Suite {
        var failures = 0

        mutating func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
            if !condition() {
                failures += 1
                fputs("FAIL: \(message)\n", stderr)
            }
        }

        mutating func expectThrows(_ message: String, _ body: () throws -> Void) {
            do {
                try body()
                failures += 1
                fputs("FAIL: \(message)\n", stderr)
            } catch {
                // Expected rejection.
            }
        }

        mutating func prepare(_ message: String, _ body: () throws -> Void) -> Bool {
            do {
                try body()
                return true
            } catch {
                failures += 1
                fputs("FAIL: \(message): \(error)\n", stderr)
                return false
            }
        }
    }

    private static let taskID = "task-123"
    private static let taskDigest = "ba5745f2c1576ebc14cb43e2e76cd3d9d135e03847bcc4f4acbdf5b4e06e08f9"

    static func main() async {
        var suite = Suite()
        let root: URL
        do {
            root = try makeTemporaryProject()
        } catch {
            fputs("FAIL: could not create test project: \(error)\n", stderr)
            Foundation.exit(1)
        }
        defer { try? FileManager.default.removeItem(at: root) }

        let sessionURL = root
            .appendingPathComponent(".work-like-musk/sessions", isDirectory: true)
            .appendingPathComponent("\(taskDigest).json")

        do {
            try writeState(initialState(projectPath: root.path), to: sessionURL)
            let state = try ProgressState.load(from: sessionURL)
            suite.expect(state.schemaVersion == 1, "loads schema version")
            suite.expect(state.projectPath == root.path, "loads canonical project path")
            suite.expect(state.taskId == taskID, "loads explicit task identity")
            suite.expect(state.title == "Build the project dashboard", "loads title")
            suite.expect(state.revision == 1, "loads positive revision")
            suite.expect(state.currentStage == nil, "allows an initial null current stage")
            suite.expect(state.stages.map(\.id) == [.question, .delete, .simplify, .accelerate, .automate], "preserves fixed stage order")
            suite.expect(state.stages.allSatisfy { $0.status == .pending }, "loads pending stage statuses")
        } catch {
            suite.failures += 1
            fputs("FAIL: valid initial state was rejected: \(error)\n", stderr)
        }

        do {
            try writeState(progressedState(projectPath: root.path), to: sessionURL)
            let state = try ProgressState.load(from: sessionURL)
            suite.expect(state.currentStage == .simplify, "loads current stage enum")
            suite.expect(state.stages[0].status == .completed, "loads completed status")
            suite.expect(state.stages[1].status == .skipped, "loads skipped status")
            suite.expect(state.stages[2].status == .inProgress, "loads in-progress status")
            suite.expect(state.stages[2].reason == "Removing avoidable branching", "loads the current reason")
            suite.expect(state.updatedAt == Date(timeIntervalSince1970: 1_788_660_002), "parses exact UTC millisecond timestamp")
        } catch {
            suite.failures += 1
            fputs("FAIL: valid progressed state was rejected: \(error)\n", stderr)
        }

        do {
            try writeState(revisitedEarlierState(projectPath: root.path), to: sessionURL)
            let state = try ProgressState.load(from: sessionURL)
            suite.expect(state.currentStage == .delete, "accepts an earlier terminal stage as the latest explicit report")
            suite.expect(state.stages[2].status == .completed, "retains valid later terminal history")
        } catch {
            suite.failures += 1
            fputs("FAIL: valid earlier-stage revisit was rejected: \(error)\n", stderr)
        }

        do {
            try writeState(clockRollbackState(projectPath: root.path), to: sessionURL)
            let state = try ProgressState.load(from: sessionURL)
            suite.expect(state.currentStage == .delete, "accepts a genuine transition after wall-clock rollback")
            suite.expect(state.stages[0].updatedAt! > state.updatedAt, "does not impose cross-stage clock monotonicity")
        } catch {
            suite.failures += 1
            fputs("FAIL: valid clock-rollback state was rejected: \(error)\n", stderr)
        }

        var missingInitialCurrent = initialState(projectPath: root.path)
        missingInitialCurrent.removeValue(forKey: "currentStage")
        expectRejected(missingInitialCurrent, at: sessionURL, message: "rejects a missing currentStage field", suite: &suite)

        var missingPendingTimestamp = initialState(projectPath: root.path)
        mutateStage(&missingPendingTimestamp, at: 4) { $0.removeValue(forKey: "updatedAt") }
        expectRejected(missingPendingTimestamp, at: sessionURL, message: "rejects a pending stage missing updatedAt", suite: &suite)

        var extraRootField = progressedState(projectPath: root.path)
        extraRootField["unexpected"] = true
        expectRejected(extraRootField, at: sessionURL, message: "rejects extra root fields", suite: &suite)

        var extraStageField = progressedState(projectPath: root.path)
        mutateStage(&extraStageField, at: 2) { $0["unexpected"] = true }
        expectRejected(extraStageField, at: sessionURL, message: "rejects extra stage fields", suite: &suite)

        var paddedReason = progressedState(projectPath: root.path)
        mutateStage(&paddedReason, at: 2) { $0["reason"] = " Removing avoidable branching " }
        expectRejected(paddedReason, at: sessionURL, message: "rejects reasons with surrounding whitespace", suite: &suite)

        var mismatchedCurrentTimestamp = progressedState(projectPath: root.path)
        mutateStage(&mismatchedCurrentTimestamp, at: 2) { $0["updatedAt"] = "2026-09-06T02:00:01.500Z" }
        expectRejected(mismatchedCurrentTimestamp, at: sessionURL, message: "rejects root and current-stage timestamp mismatch", suite: &suite)

        var malformed = progressedState(projectPath: root.path)
        malformed["stages"] = "not-an-array"
        expectRejected(malformed, at: sessionURL, message: "rejects malformed JSON shape instead of creating default progress", suite: &suite)

        var foreignProject = progressedState(projectPath: root.path)
        foreignProject["projectPath"] = root.deletingLastPathComponent().path
        expectRejected(foreignProject, at: sessionURL, message: "rejects a state whose project identity does not match its path", suite: &suite)

        var noncanonicalProject = progressedState(projectPath: root.path)
        noncanonicalProject["projectPath"] = root.path + "/."
        expectRejected(noncanonicalProject, at: sessionURL, message: "rejects a noncanonical spelling of the bound project path", suite: &suite)

        let foreignURL = sessionURL.deletingLastPathComponent().appendingPathComponent("44bf258ecc21c1ec994e3af0a5a6206f337aedbfeab064768d7361062f55c0d8.json")
        expectRejected(progressedState(projectPath: root.path), at: foreignURL, message: "rejects a state whose task digest does not match its filename", suite: &suite)

        var unknownStatus = progressedState(projectPath: root.path)
        mutateStage(&unknownStatus, at: 2) { $0["status"] = "paused" }
        expectRejected(unknownStatus, at: sessionURL, message: "rejects an unknown status enum", suite: &suite)

        var wrongOrder = progressedState(projectPath: root.path)
        if var stages = wrongOrder["stages"] as? [[String: Any]] {
            stages.swapAt(0, 1)
            wrongOrder["stages"] = stages
        }
        expectRejected(wrongOrder, at: sessionURL, message: "rejects reordered stage identifiers", suite: &suite)

        var invalidTimestamp = progressedState(projectPath: root.path)
        invalidTimestamp["updatedAt"] = "2026-09-06T02:00:02Z"
        expectRejected(invalidTimestamp, at: sessionURL, message: "rejects timestamps without UTC milliseconds", suite: &suite)

        var impossibleTimestamp = progressedState(projectPath: root.path)
        impossibleTimestamp["updatedAt"] = "2026-02-30T02:00:02.000Z"
        expectRejected(impossibleTimestamp, at: sessionURL, message: "rejects impossible calendar timestamps", suite: &suite)

        var invalidPending = initialState(projectPath: root.path)
        mutateStage(&invalidPending, at: 0) { $0["reason"] = "Already started" }
        expectRejected(invalidPending, at: sessionURL, message: "rejects pending stages carrying stale detail", suite: &suite)

        var outOfOrder = progressedState(projectPath: root.path)
        mutateStage(&outOfOrder, at: 0) {
            $0["status"] = "pending"
            $0["reason"] = ""
            $0["updatedAt"] = NSNull()
        }
        expectRejected(outOfOrder, at: sessionURL, message: "rejects progress that bypasses an earlier pending stage", suite: &suite)

        var twoActive = progressedState(projectPath: root.path)
        mutateStage(&twoActive, at: 1) { $0["status"] = "blocked" }
        expectRejected(twoActive, at: sessionURL, message: "rejects more than one active or blocked stage", suite: &suite)

        var wrongCurrent = progressedState(projectPath: root.path)
        wrongCurrent["currentStage"] = "delete"
        expectRejected(wrongCurrent, at: sessionURL, message: "rejects currentStage that differs from the active stage", suite: &suite)

        var missingCurrent = progressedState(projectPath: root.path)
        missingCurrent["currentStage"] = NSNull()
        expectRejected(missingCurrent, at: sessionURL, message: "rejects null currentStage when any stage has been reported", suite: &suite)

        var blankTitle = progressedState(projectPath: root.path)
        blankTitle["title"] = "   "
        expectRejected(blankTitle, at: sessionURL, message: "rejects blank trimmed titles", suite: &suite)

        var overlongUnicodeTitle = progressedState(projectPath: root.path)
        overlongUnicodeTitle["title"] = String(repeating: "e\u{301}", count: 61)
        expectRejected(overlongUnicodeTitle, at: sessionURL, message: "counts Unicode scalars consistently with the Python writer", suite: &suite)

        do {
            let oversized = Data(repeating: 0x20, count: 65_537)
            try oversized.write(to: sessionURL)
            suite.expectThrows("rejects state files larger than 64 KiB") {
                _ = try ProgressState.load(from: sessionURL)
            }
        } catch {
            suite.failures += 1
            fputs("FAIL: could not prepare oversized state: \(error)\n", stderr)
        }

        do {
            try writeState(progressedState(projectPath: root.path), to: sessionURL)
            await MainActor.run {
                let store = ProgressStateStore()
                store.bind(to: sessionURL)
                suite.expect(store.snapshot?.revision == 3, "store publishes a valid bound snapshot")
                suite.expect(store.errorMessage == nil, "store clears errors after a valid read")

                if suite.prepare("could not prepare malformed same-binding state", {
                    try Data("{broken".utf8).write(to: sessionURL)
                }) {
                    store.refresh()
                    suite.expect(store.snapshot?.revision == 3, "store retains the last good snapshot after a same-binding error")
                    suite.expect(store.errorMessage != nil, "store visibly reports a same-binding read error")
                }

                let invalidOther = sessionURL.deletingLastPathComponent().appendingPathComponent("new-session.json")
                store.bind(to: invalidOther)
                suite.expect(store.snapshot == nil, "store clears old progress when explicitly rebound")
                suite.expect(store.errorMessage != nil, "store reports an invalid fresh binding")
            }
        } catch {
            suite.failures += 1
            fputs("FAIL: could not prepare store test: \(error)\n", stderr)
        }

        if suite.failures == 0 {
            print("PASS: ProgressState decoder and store")
        }
        Foundation.exit(suite.failures == 0 ? 0 : 1)
    }

    private static func makeTemporaryProject() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("FiveStepHUDTests-\(UUID().uuidString)", isDirectory: true)
            .standardizedFileURL
        let sessions = root.appendingPathComponent(".work-like-musk/sessions", isDirectory: true)
        try FileManager.default.createDirectory(at: sessions, withIntermediateDirectories: true)
        return root
    }

    private static func initialState(projectPath: String) -> [String: Any] {
        [
            "schemaVersion": 1,
            "projectPath": projectPath,
            "taskId": taskID,
            "title": "Build the project dashboard",
            "revision": 1,
            "updatedAt": "2026-09-06T02:00:00.000Z",
            "currentStage": NSNull(),
            "stages": [
                stage("question"), stage("delete"), stage("simplify"),
                stage("accelerate"), stage("automate")
            ]
        ]
    }

    private static func progressedState(projectPath: String) -> [String: Any] {
        [
            "schemaVersion": 1,
            "projectPath": projectPath,
            "taskId": taskID,
            "title": "Build the project dashboard",
            "revision": 3,
            "updatedAt": "2026-09-06T02:00:02.000Z",
            "currentStage": "simplify",
            "stages": [
                stage("question", status: "completed", reason: "Requirements are evidence-based", updatedAt: "2026-09-06T02:00:00.000Z"),
                stage("delete", status: "skipped", reason: "Nothing safe to remove", updatedAt: "2026-09-06T02:00:01.000Z"),
                stage("simplify", status: "in_progress", reason: "Removing avoidable branching", updatedAt: "2026-09-06T02:00:02.000Z"),
                stage("accelerate"),
                stage("automate")
            ]
        ]
    }

    private static func revisitedEarlierState(projectPath: String) -> [String: Any] {
        [
            "schemaVersion": 1,
            "projectPath": projectPath,
            "taskId": taskID,
            "title": "Build the project dashboard",
            "revision": 5,
            "updatedAt": "2026-09-06T02:00:04.000Z",
            "currentStage": "delete",
            "stages": [
                stage("question", status: "completed", reason: "Requirements are evidence-based", updatedAt: "2026-09-06T02:00:00.000Z"),
                stage("delete", status: "skipped", reason: "Reconfirmed as unnecessary", updatedAt: "2026-09-06T02:00:04.000Z"),
                stage("simplify", status: "completed", reason: "Simplification is complete", updatedAt: "2026-09-06T02:00:02.000Z"),
                stage("accelerate"),
                stage("automate")
            ]
        ]
    }

    private static func clockRollbackState(projectPath: String) -> [String: Any] {
        [
            "schemaVersion": 1,
            "projectPath": projectPath,
            "taskId": taskID,
            "title": "Build the project dashboard",
            "revision": 4,
            "updatedAt": "2026-09-06T02:00:05.000Z",
            "currentStage": "delete",
            "stages": [
                stage("question", status: "completed", reason: "Requirements checked", updatedAt: "2026-09-06T02:00:10.000Z"),
                stage("delete", status: "in_progress", reason: "Reviewing removable scope", updatedAt: "2026-09-06T02:00:05.000Z"),
                stage("simplify"),
                stage("accelerate"),
                stage("automate")
            ]
        ]
    }

    private static func stage(
        _ id: String,
        status: String = "pending",
        reason: String = "",
        updatedAt: Any = NSNull()
    ) -> [String: Any] {
        ["id": id, "status": status, "reason": reason, "updatedAt": updatedAt]
    }

    private static func mutateStage(
        _ state: inout [String: Any],
        at index: Int,
        mutation: (inout [String: Any]) -> Void
    ) {
        guard var stages = state["stages"] as? [[String: Any]] else { return }
        mutation(&stages[index])
        state["stages"] = stages
    }

    private static func writeState(_ value: [String: Any], to url: URL) throws {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }

    private static func expectRejected(
        _ value: [String: Any],
        at url: URL,
        message: String,
        suite: inout Suite
    ) {
        guard suite.prepare("could not prepare fixture for '\(message)'", {
            try writeState(value, to: url)
        }) else { return }
        suite.expectThrows(message) {
            _ = try ProgressState.load(from: url)
        }
    }
}
