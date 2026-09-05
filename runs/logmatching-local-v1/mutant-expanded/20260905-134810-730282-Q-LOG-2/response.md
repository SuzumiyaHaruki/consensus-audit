{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "The follower append-acceptance path in log.go resolves conflicts based only on index and term, ignoring Entry kind and payload. Additionally, maybeAppend's special case skips conflict checking for an incoming empty first entry when the follower's last index matches it and the next incoming entry is non-empty. This can allow a follower to retain an existing diverging entry at the first index while appending later entries from the leader, after which both nodes may share the same term at a later index but differ in an earlier prefix entry, violating Q-LOG-2. Reachability of the required initial divergence is plausible but not fully proven by execution.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 136,
      "claim": "maybeAppend first checks only the previous entry term via matchTerm, then conditionally drops the first incoming entry from conflict checking when it is empty, has the follower's last index, and the next entry is non-empty. It later calls findConflict on the remaining entries and appends only from the returned conflict index onward."
    },
    {
      "path": "log.go",
      "start_line": 159,
      "end_line": 172,
      "claim": "findConflict considers an entry conflicting only if its (index,term) pair does not match the local log; it does not compare Entry type or payload."
    },
    {
      "path": "log.go",
      "start_line": 452,
      "end_line": 458,
      "claim": "matchTerm returns true exactly when the stored term at the given index equals the supplied term, ignoring Entry kind and payload."
    },
    {
      "path": "raft.go",
      "start_line": 616,
      "end_line": 660,
      "claim": "maybeSendAppend constructs MsgApp from the leader's log starting at pr.Next, including all available entries; these are later passed to the follower's maybeAppend."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1798,
      "claim": "handleAppendEntries converts the MsgApp into a logSlice without validating its contents and calls raftLog.maybeAppend; if maybeAppend reports success, it sends an acknowledgement for the new last index."
    }
  ],
  "mechanism": {
    "violated_obligation": "Before appending entries from a MsgApp, the follower must ensure its existing log prefix is identical to the leader's prefix through every received entry. In particular, if an incoming entry shares an index with an existing local entry, any difference in term, kind, or payload must force truncation before appending later entries.",
    "decisive_relation": "maybeAppend's special-case skips conflict checking for an empty first incoming entry when the follower's last index equals its index and the next incoming entry has non-empty data. Since findConflict compares only (index,term), the skipped first entry may have a different term and/or payload than the follower's existing entry at that index. Conflict detection then starts at the next index, and only the later entries are appended, preserving the divergent local prefix."
  },
  "causal_chain": [
    "A leader sends a MsgApp containing an empty entry at index i and a non-empty entry at index i+1, both in the leader's current term, anchored at index i-1.",
    "A follower whose last index is i and whose existing entry at i differs from the incoming empty entry receives the MsgApp; handleAppendEntries calls maybeAppend, and the special-case drops the first entry from conflict checking.",
    "findConflict only examines index and term, so it returns i+1 as the first conflict rather than i; maybeAppend appends from i+1 onward, leaving the divergent existing entry at i in place.",
    "The follower now has a later entry with the same term as the leader, but its prefix through that index differs at index i, contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "A fixed-membership Raft cluster. Follower F has a logical log whose last index is i, with an entry at index i whose term or payload differs from the leader's incoming empty entry at i. Leader L has an empty entry at index i in term T_new and a non-empty entry at index i+1 in the same term T_new. L's Progress for F has Next <= i, so MsgApp will include both entries.",
    "actions": [
      "A1: L becomes leader at term T_new and appends an empty entry at index i.",
      "A2: L appends a non-empty proposal at index i+1, also at term T_new.",
      "A3: L sends MsgApp to F anchored at i-1 with Entries = [entry i: term T_new, empty payload; entry i+1: term T_new, non-empty payload] and Commit >= i+1.",
      "A4: F receives and processes the MsgApp via handleAppendEntries and maybeAppend; it appends entry i+1 but keeps its existing entry i.",
      "A5: After persistence, inspect both nodes' logical logs at indexes i and i+1."
    ],
    "violation": "Both F and L contain an entry at index i+1 with term T_new, but their entries at index i differ in term and/or payload, violating Q-LOG-2.",
    "oracle": "Compare durable logical-log entries at indexes i and i+1 on F and L. Assert that if the terms at index i+1 are equal, then the terms, kinds, and payloads at every index 1..i+1 must be identical. The test fails if index i differs while index i+1 matches in term."
  },
  "uncertainties": [
    "The reachability of a follower having an existing entry at index i with a different term/payload while the leader simultaneously has an empty entry at that index and a non-empty entry at i+1 in its current term is not fully established; it may depend on crash-and-uncommitted-tail divergence.",
    "No downstream execution or deterministic test was performed; this is a static, code-supported hypothesis.",
    "The limited diagnostic boundary did not exhaustively inspect snapshot restoration, asynchronous storage races, or all message-term filtering that might prevent the divergent input state from occurring."
  ]
}
