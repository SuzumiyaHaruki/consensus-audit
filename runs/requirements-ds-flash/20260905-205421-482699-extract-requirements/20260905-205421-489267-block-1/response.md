```json
{
  "requirements": [
    {
      "id": "B1-1",
      "operation": [
        "Log entries flow only from the leader to other servers",
        "Log-entry flow is unidirectional (leader to other servers) under the strong-leader model"
      ],
      "category": "protocol_requirement",
      "applies_when": "Global property of Raft log replication whenever a leader is replicating log entries",
      "requirement": "Raft uses a stronger form of leadership than other consensus algorithms: log entries only flow from the leader to other servers.",
      "definitions": [],
      "source_refs": [
        {
          "block_id": "raft-extended:p1:l1",
          "start_line": 15,
          "end_line": 18
        }
      ],
      "origin": "explicit",
      "review_status": "pending"
    },
    {
      "id": "B1-2",
      "operation": [
        "Elect leaders using randomized timers",
        "Layer the randomized election-timer mechanism on the heartbeats already required by the consensus algorithm",
        "Resolve election conflicts through the randomized timers simply and rapidly"
      ],
      "category": "protocol_requirement",
      "applies_when": "Leader election (mechanism-level property of Basic Raft)",
      "requirement": "Leader election in Raft uses randomized timers; this adds only a small amount of mechanism to the heartbeats already required for any consensus algorithm while resolving conflicts simply and rapidly.",
      "definitions": [],
      "source_refs": [
        {
          "block_id": "raft-extended:p1:l1",
          "start_line": 19,
          "end_line": 22
        }
      ],
      "origin": "explicit",
      "review_status": "pending"
    }
  ],
  "assumptions": [],
  "unresolved": [],
  "block_results": [
    {
      "block_id": "raft-extended:p1:l1",
      "requirement_ids": [
        "B1-1",
        "B1-2"
      ],
      "reason": "Title/abstract page. Extracted the two explicit global Basic-Raft behaviors stated here: leader-only log-entry flow (lines 15-18) and randomized-timer leader election (lines 19-22). Remaining text is motivation, evaluation, paper outline, or design-goal statements. The joint-consensus membership-change claims (lines 23-27 and 47-48) describe the cluster-membership mechanism, which is outside the configured fixed-membership scope, so they were not imported as applicable requirements."
    }
  ]
}
```
