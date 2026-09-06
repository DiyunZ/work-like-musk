import Foundation

@main
struct StageReadinessTests {
    static func state(_ statuses: [ProgressState.Status]) -> ProgressState {
        let stages = zip(ProgressState.StageID.allCases, statuses).map {
            ProgressState.Stage(id: $0.0, status: $0.1, reason: "", updatedAt: nil)
        }
        return ProgressState(schemaVersion: 1, projectPath: "/fixture", taskId: "fixture", title: "Fixture",
                             revision: 1, updatedAt: Date(), currentStage: nil, stages: stages)
    }
    static func main() {
        precondition(state([.pending, .pending, .pending, .pending, .pending]).waitingStageID == .question)
        precondition(state([.inProgress, .pending, .pending, .pending, .pending]).waitingStageID == nil)
        precondition(state([.completed, .pending, .pending, .pending, .pending]).waitingStageID == .delete)
        precondition(state([.completed, .skipped, .pending, .pending, .pending]).waitingStageID == .simplify)
        precondition(state([.completed, .blocked, .pending, .pending, .pending]).waitingStageID == nil)
        precondition(state([.completed, .completed, .completed, .completed, .completed]).waitingStageID == nil)
        precondition(state([.pending, .pending, .pending, .pending, .pending]).flowingConnectorIndex == nil)
        precondition(state([.inProgress, .pending, .pending, .pending, .pending]).flowingConnectorIndex == nil)
        precondition(state([.completed, .pending, .pending, .pending, .pending]).flowingConnectorIndex == 0)
        precondition(state([.completed, .inProgress, .pending, .pending, .pending]).flowingConnectorIndex == 0)
        precondition(state([.completed, .skipped, .pending, .pending, .pending]).flowingConnectorIndex == 1)
        precondition(state([.completed, .completed, .inProgress, .pending, .pending]).flowingConnectorIndex == 1)
        precondition(state([.completed, .blocked, .pending, .pending, .pending]).flowingConnectorIndex == nil)
        precondition(state([.completed, .completed, .completed, .completed, .pending]).flowingConnectorIndex == 3)
        precondition(state([.completed, .completed, .completed, .completed, .completed]).flowingConnectorIndex == nil)
        print("PASS: only the next eligible pending step waits; active, blocked and finished workflows do not advance")
    }
}
