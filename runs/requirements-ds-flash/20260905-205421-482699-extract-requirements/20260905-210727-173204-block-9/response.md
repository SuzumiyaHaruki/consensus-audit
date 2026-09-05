```json
{
  "requirements": [
    {
      "id": "B9-R-01",
      "operation": [
        "maintain currentTerm, votedFor, and log[] as persistent state on stable storage on every server",
        "update persistent state on stable storage before responding to RPCs"
      ],
      "category": "protocol_requirement",
      "applies_when": "All servers at all times, in particular when handling an RPC that can change currentTerm, votedFor, or log[].",
      "requirement": "Every server stores currentTerm, votedFor, and log[] as persistent state on stable storage; updates to this persistent state are written to stable storage before the server responds to RPCs.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 2, "end_line": 10},
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 3, "end_line": 5}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 2, "end_line": 10}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-02",
      "operation": [
        "initialize currentTerm to 0 on first boot",
        "record in currentTerm the latest term the server has seen",
        "increase currentTerm monotonically, never decreasing it"
      ],
      "category": "protocol_requirement",
      "applies_when": "Every server, from first boot and thereafter (including across restarts).",
      "requirement": "currentTerm holds the latest term the server has seen; it is initialized to 0 on first boot and increases monotonically.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 4, "end_line": 5}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 4, "end_line": 5}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-03",
      "operation": [
        "store in votedFor the candidateId that received this server's vote in the current term",
        "store null in votedFor when no candidate has received this server's vote in the current term"
      ],
      "category": "protocol_requirement",
      "applies_when": "Every server, whenever it votes or has not yet voted in the current term.",
      "requirement": "votedFor records the candidateId that received this server's vote in the current term, or null if no vote has been granted in the current term.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 6, "end_line": 7}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 6, "end_line": 7}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-04",
      "operation": [
        "store the server's log as the ordered list log[]",
        "store in each log entry the command for the state machine",
        "store in each log entry the term in which the entry was received by the leader",
        "number log entries starting at index 1"
      ],
      "category": "protocol_requirement",
      "applies_when": "Every server maintaining its replicated log.",
      "requirement": "Each server's log[] holds log entries; every entry contains the command for the state machine and the term in which the entry was received by the leader, and the first log index is 1.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 8, "end_line": 10}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 8, "end_line": 10}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-05",
      "operation": [
        "maintain commitIndex as the index of the highest log entry known to be committed",
        "initialize commitIndex to 0",
        "increase commitIndex monotonically"
      ],
      "category": "protocol_requirement",
      "applies_when": "All servers; commitIndex is volatile state.",
      "requirement": "On every server, commitIndex is volatile state recording the index of the highest log entry known to be committed; it is initialized to 0 and increases monotonically.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 13, "end_line": 15}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 12, "end_line": 15}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-06",
      "operation": [
        "maintain lastApplied as the index of the highest log entry applied to the state machine",
        "initialize lastApplied to 0",
        "increase lastApplied monotonically"
      ],
      "category": "protocol_requirement",
      "applies_when": "All servers; lastApplied is listed as volatile state in Figure 2.",
      "requirement": "On every server, lastApplied records the index of the highest log entry applied to the state machine; it is initialized to 0 and increases monotonically.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 16, "end_line": 18}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 12, "end_line": 18}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-07",
      "operation": [
        "reinitialize the leader-only volatile state (nextIndex[] and matchIndex[]) after an election in which a server becomes leader"
      ],
      "category": "protocol_requirement",
      "applies_when": "A server that has just won an election and become leader.",
      "requirement": "The leader-only volatile state, consisting of nextIndex[] and matchIndex[], is reinitialized after an election when a server becomes leader.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 19, "end_line": 26}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 19, "end_line": 20}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-08",
      "operation": [
        "maintain nextIndex[] with one entry per server",
        "set nextIndex[server] to the index of the next log entry to send to that server",
        "initialize nextIndex[] for every server to the leader's last log index + 1 after an election"
      ],
      "category": "protocol_requirement",
      "applies_when": "Leader, from the moment it becomes leader (leader-only volatile state).",
      "requirement": "For each server, the leader's nextIndex[] records the index of the next log entry to send to that server; after an election, nextIndex for every server is initialized to the leader's last log index + 1.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 21, "end_line": 23}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 19, "end_line": 23}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    },
    {
      "id": "B9-R-09",
      "operation": [
        "maintain matchIndex[] with one entry per server",
        "set matchIndex[server] to the index of the highest log entry known to be replicated on that server",
        "initialize matchIndex[] for every server to 0",
        "increase matchIndex entries monotonically"
      ],
      "category": "protocol_requirement",
      "applies_when": "Leader, from the moment it becomes leader (leader-only volatile state).",
      "requirement": "For each server, the leader's matchIndex[] records the index of the highest log entry known to be replicated on that server; entries are initialized to 0 and increase monotonically.",
      "definitions": [
        {"block_id": "raft-extended:figure2:1", "start_line": 24, "end_line": 26}
      ],
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 19, "end_line": 26}
      ],
      "origin": "explicit",
      "derivation": "",
      "review_status": "pending"
    }
  ],
  "assumptions": [
    {
      "id": "B9-A-01",
      "assumption": "A node may crash and later restart with the same identity; a crash loses all volatile state and performs no graceful flushing; after restart a node sees only writes that completed durable persistence before the crash.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 3, "end_line": 5}
      ],
      "review_status": "pending"
    },
    {
      "id": "B9-A-02",
      "assumption": "Completed durable writes are not corrupted; the network may delay, drop, duplicate, reorder, and later resume messages but does not forge or modify protocol content; nodes are not Byzantine.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 6, "end_line": 9}
      ],
      "review_status": "pending"
    },
    {
      "id": "B9-A-03",
      "assumption": "The fault model does not itself define the cluster size, quorum rule, membership scheme, or failure counts under which progress is required; those are supplied by the selected protocol and experiment configuration, which here selects fixed membership, so the Figure 2 'all servers' quantifier is interpreted over members of a fixed-membership cluster.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 12, "end_line": 12},
        {"block_id": "etcd-raft-boundary:p0:l1", "start_line": 10, "end_line": 11}
      ],
      "review_status": "pending"
    }
  ],
  "unresolved": [
    {
      "id": "B9-U-01",
      "issue": "Figure 2 classifies lastApplied as volatile state on all servers, but the dissertation states lastApplied must be as persistent as the state machine (persistent for a persistent state machine) and its errata makes the same correction to the cheatsheet. The classification that applies to the audited target (including its synchronous/asynchronous storage modes) must be reconciled rather than silently choosing either interpretation.",
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 16, "end_line": 18},
        {"block_id": "dissertation:p44:l5", "start_line": 13, "end_line": 16},
        {"block_id": "dissertation-errata:p0:l35", "start_line": 3, "end_line": 3}
      ],
      "review_status": "pending"
    },
    {
      "id": "B9-U-02",
      "issue": "Figure 2 states the first log index is 1, while log compaction/snapshotting (included in the experiment boundary) truncates the log prefix through the last snapshot-included index, so a snapshotted log's first retained index can exceed 1. How the 'first index is 1' rule relates to snapshotted/supported target state must be reconciled.",
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 8, "end_line": 10},
        {"block_id": "dissertation:p65:l1", "start_line": 5, "end_line": 13},
        {"block_id": "dissertation:p68:l20", "start_line": 15, "end_line": 18},
        {"block_id": "etcd-raft-boundary:p0:l1", "start_line": 15, "end_line": 15}
      ],
      "review_status": "pending"
    },
    {
      "id": "B9-U-03",
      "issue": "Figure 2 requires persistent state to be updated on stable storage before responding to RPCs, but the experiment boundary includes both synchronous and asynchronous storage-processing modes; the paper does not specify an asynchronous completion/publication API, so how the before-responding rule is realized in asynchronous storage modes requires target-version design/API evidence.",
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 2, "end_line": 3},
        {"block_id": "etcd-raft-boundary:p0:l1", "start_line": 13, "end_line": 13}
      ],
      "review_status": "pending"
    },
    {
      "id": "B9-U-04",
      "issue": "The text of this Figure 2 box was produced by a Poppler extraction that is not human approved, so the exact wording of the state-variable definitions extracted here is subject to confirmation against the cached PDF before final review.",
      "source_refs": [
        {"block_id": "raft-extended:figure2:1", "start_line": 1, "end_line": 26}
      ],
      "review_status": "pending"
    }
  ],
  "block_results": [
    {
      "block_id": "raft-extended:figure2:1",
      "requirement_ids": [
        "B9-R-01",
        "B9-R-02",
        "B9-R-03",
        "B9-R-04",
        "B9-R-05",
        "B9-R-06",
        "B9-R-07",
        "B9-R-08",
        "B9-R-09"
      ],
      "reason": "Extracted the Figure 2 State-box definitions and invariants (persistent-state set and durability-before-response rule, per-variable initialization/monotonicity and content rules, and leader-state reinitialization) as explicit protocol requirements; classification conflicts (lastApplied persistence, first-log-index versus snapshots, sync versus async storage) are recorded as unresolved."
    }
  ]
}
```