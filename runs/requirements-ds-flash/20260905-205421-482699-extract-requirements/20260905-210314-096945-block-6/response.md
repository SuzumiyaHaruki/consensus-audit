```json
{
  "requirements": [
    {
      "id": "B6-1",
      "operation": [
        "Append new log entries sequentially in a constrained order to a single replicated log.",
        "Maintain the log without holes, so existing entries occupy consecutive indices with no unfilled index positions."
      ],
      "category": "protocol_requirement",
      "applies_when": "For every server at all times while it maintains or extends its log as part of the Raft consensus protocol.",
      "requirement": "Raft is designed around a single sequential log: new entries are appended sequentially in a constrained order, and logs are not allowed to have holes (log entries occupy consecutive indices without gaps).",
      "definitions": [],
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 5, "end_line": 7},
        {"block_id": "raft-extended:p3:l1", "start_line": 34, "end_line": 35}
      ],
      "origin": "explicit",
      "derivation": "Not applicable; the property is stated directly in the cited passages.",
      "review_status": "pending"
    },
    {
      "id": "B6-2",
      "operation": [
        "Constrain the ways in which logs on different servers may become inconsistent with each other.",
        "Keep inter-server log divergence within limited, algorithmically reconcilable forms rather than allowing arbitrary divergence."
      ],
      "category": "protocol_requirement",
      "applies_when": "Whenever logs of different servers are compared or reconciled, e.g., during log replication under a newly elected leader.",
      "requirement": "Raft limits the ways in which logs can become inconsistent with each other: divergence between server logs is constrained rather than arbitrary.",
      "definitions": [],
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 35, "end_line": 36}
      ],
      "origin": "explicit",
      "derivation": "Not applicable; the property is stated directly in the cited passage.",
      "review_status": "pending"
    },
    {
      "id": "B6-3",
      "operation": [
        "Employ randomization in the Raft leader election algorithm.",
        "Handle otherwise nondeterministic election choices in a uniform fashion (choose any; it does not matter) through randomized approaches."
      ],
      "category": "protocol_requirement",
      "applies_when": "During leader election.",
      "requirement": "Raft's leader election algorithm uses randomization: randomized approaches introduce nondeterminism, and Raft uses randomization to simplify leader election.",
      "definitions": [],
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 36, "end_line": 40}
      ],
      "origin": "explicit",
      "derivation": "Not applicable; the use of randomization for leader election is stated directly in the cited passage.",
      "review_status": "pending"
    },
    {
      "id": "B6-4",
      "operation": [
        "Elect a leader before coordinating a series of decisions.",
        "Have the elected leader coordinate the series of log/consensus decisions rather than relying on symmetric peer-to-peer agreement."
      ],
      "category": "protocol_requirement",
      "applies_when": "When a cluster must make a series of decisions (normal operation).",
      "requirement": "Raft is leader-coordinated: rather than using a symmetric peer-to-peer approach for a series of decisions, Raft first elects a leader and then has that leader coordinate the decisions.",
      "definitions": [],
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 11, "end_line": 14}
      ],
      "origin": "explicit",
      "derivation": "Not applicable; the leader-first design choice for a series of decisions is stated directly in the cited passage.",
      "review_status": "pending"
    }
  ],
  "assumptions": [
    {
      "id": "B6-A1",
      "assumption": "Under the crash-recovery fault model, a node may crash and later restart with the same identity; a crash loses all volatile state with no graceful flushing, and after restart the node observes only writes whose durable persistence completed before the crash.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 3, "end_line": 5}
      ],
      "review_status": "pending"
    },
    {
      "id": "B6-A2",
      "assumption": "The network may delay, drop, duplicate, reorder, and later resume messages; it does not forge messages or modify their protocol content, and nodes are not Byzantine.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 6, "end_line": 8}
      ],
      "review_status": "pending"
    },
    {
      "id": "B6-A3",
      "assumption": "Safety of the extracted protocol properties must hold even without a live quorum or eventual message delivery; the fault model does not itself define cluster size, quorum rule, membership scheme, or the number of failures under which progress is required.",
      "source_refs": [
        {"block_id": "crash-recovery-cft:p0:l1", "start_line": 10, "end_line": 12}
      ],
      "review_status": "pending"
    }
  ],
  "unresolved": [
    {
      "id": "B6-U1",
      "issue": "This block is motivation and design rationale (what is wrong with Paxos; designing for understandability), not the operative algorithm section. It is ambiguous whether its normative-sounding statements (logs not allowed to have holes; Raft limits ways logs become inconsistent; randomization used in leader election) are independent binding constraints on an implementation or summary justifications whose exact meaning is fixed only by Figure 2 and Section 5.",
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 25, "end_line": 40}
      ],
      "review_status": "pending"
    },
    {
      "id": "B6-U2",
      "issue": "The no-hole statement is not reconciled with log compaction/snapshotting, where earlier log entries are removed or represented by a snapshot. The precise boundary between a hole-free log and a log whose prefix has been truncated by a snapshot must be resolved before applying this invariant to a snapshotting implementation.",
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 34, "end_line": 35}
      ],
      "review_status": "pending"
    },
    {
      "id": "B6-U3",
      "issue": "PDF text conversion appears to run the sentence 'The following comment from the Chubby implementers is typical:' directly into text describing Raft's own design choices ('There were numerous points in the design of Raft...'), with blank line 18 as the only boundary marker. Quotation/paragraph boundaries may be lost, so attribution of lines 19-24 (quoted material vs. the authors' Section 4 prose) is uncertain and should be checked against the cached PDF.",
      "source_refs": [
        {"block_id": "raft-extended:p3:l1", "start_line": 15, "end_line": 24}
      ],
      "review_status": "pending"
    }
  ],
  "block_results": [
    {
      "block_id": "raft-extended:p3:l1",
      "requirement_ids": ["B6-1", "B6-2", "B6-3", "B6-4"],
      "reason": "Extracted explicit design-level protocol properties stated in this page's rationale text: sequential constrained log appends with no holes, constrained inter-server log divergence, randomized leader election, and leader-coordinated decision making. The remaining passages are criticism of Paxos, methodological preferences (understandability, problem decomposition), and possible conversion artifacts, and were not turned into requirements."
    }
  ]
}
```