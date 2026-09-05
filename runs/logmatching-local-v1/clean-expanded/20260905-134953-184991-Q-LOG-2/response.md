{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "The follower append-acceptance path reduces entry identity to (index, term) via pbEntryID and matchTerm. It does not compare kind or payload when an incoming MsgApp overlaps an existing local entry. A same-term overlap with different kind/payload is treated as a match, the local entry is retained, and the follower sends a successful MsgAppResp. This can leave two nodes with the same term at an index but different payloads/prefixes, violating Q-LOG-2. The main limitation is that the reviewed path does not establish a reachable protocol-generated message with same (index, term) but different payload; the scenario may require prior inconsistency or direct state injection.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 128,
      "claim": "maybeAppend returns ok true after matching prev term. It calls findConflict and, when ci == 0, performs no append and returns success. Thus overlapping entries with the same term at the same index are accepted without replacing the local entry."
    },
    {
      "path": "log.go",
      "start_line": 142,
      "end_line": 165,
      "claim": "findConflict returns the first index where l.matchTerm(id) is false. id is pbEntryID, so the conflict test only checks term. If the term matches, ci remains 0 even when kind or payload differs."
    },
    {
      "path": "types.go",
      "start_line": 23,
      "end_line": 36,
      "claim": "entryID contains only term and index. pbEntryID builds the ID from Entry.Term and Entry.Index, deliberately omitting Entry.Type and Entry.Data, so term/index equality is treated as full entry identity."
    },
    {
      "path": "log.go",
      "start_line": 445,
      "end_line": 451,
      "claim": "matchTerm only compares the term returned for the index. It does not inspect Entry kind or payload."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1798,
      "claim": "handleAppendEntries calls maybeAppend. If maybeAppend returns ok, the follower sends a non-reject MsgAppResp with mlastIndex, so the sender believes the log matched."
    }
  ],
  "mechanism": {
    "violated_obligation": "When accepting a MsgApp that overlaps an existing local entry, the follower must verify that the overlapping entry is identical in term, kind, and payload, and otherwise truncate and replace the conflicting suffix. Q-LOG-2 requires that same (index, term) implies identical prefix, so term equality alone is insufficient if kind/payload can differ.",
    "decisive_relation": "l.findConflict(a.entries) detects a conflict only when l.matchTerm(id) is false. l.matchTerm uses entryID{term, index}, which ignores Entry.Type and Entry.Data. Therefore a same-index, same-term overlap with different kind or payload yields ci == 0, causing maybeAppend to return ok without replacing the local entry."
  },
  "causal_chain": [
    "Node B has an existing logical-log entry e_old=(i, T, kind_old, payload_old).",
    "Node B receives a MsgApp whose prev entry matches and whose overlapping entry is e_new=(i, T, kind_new, payload_new) with different kind/payload.",
    "findConflict returns 0 because pbEntryID(e_new) has the same term and index as e_old; maybeAppend performs no append and returns ok.",
    "B publishes a successful MsgAppResp. After completion, A and B both contain index i with term T, but their entries at i differ, contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "Two nodes A and B. B has committed index 0. B's logical log contains index 1 term 1 payload 'x' and index 2 term 1 payload 'x' (the prev entry at index 1 matches A). A's logical log contains index 1 term 1 payload 'x' and index 2 term 1 payload 'y'. Both share term 1.",
    "actions": [
      "A1: Deliver MsgApp from A to B with Index=1, LogTerm=1, Entries=[{Index:2, Term:1, Type:EntryNormal, Data:\"y\"}], and Commit=0 or 1.",
      "A2: Observe B's resulting logical log and the MsgAppResp returned to A."
    ],
    "violation": "After handling the MsgApp, B still has EntryNormal payload 'x' at index 2 term 1, while A has EntryNormal payload 'y' at the same index and term. Thus both nodes contain the same term at index i=2 but differ in payload, negating Q-LOG-2.",
    "oracle": "After processing the MsgApp, verify that B's entry at index 2 term 1 is still payload 'x' and that B returned a non-reject MsgAppResp with Index=2. Then verify A's corresponding entry at index 2 term 1 is payload 'y'."
  },
  "uncertainties": [
    "Reachability from internally generated protocol traffic was not established: in a correct Raft execution, the same (index, term) should imply the same kind and payload, so the required differing A state may need direct injection or a prior defect.",
    "No execution was performed; the contradiction is based on inspected source behavior rather than an executed trace.",
    "The scenario uses a manually constructed differing payload at the same index and term, which may be outside the normal crash-recovery operation of the target library."
  ]
}
