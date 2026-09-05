{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "maybeAppend contains a conflict-check bypass for a leading empty no-op entry when followed by a non-empty entry. This can leave a follower's existing conflicting entry at its current tail while the follower accepts the subsequent entry and publishes success, causing two nodes to have identical term at one index but non-identical prefixes, violating log matching.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 135,
      "claim": "maybeAppend first validates only a.prev via matchTerm. Lines 116-121 remove check[0] from conflict detection if it is an empty entry at the follower's last index and check[1] is non-empty. Lines 122-133 then findConflict on the shortened check and append from the conflict index onward. With check[0] removed, a conflict at the follower's current last index is not detected, and a.entries[1:] can be appended while the old entry at check[0].Index remains."
    },
    {
      "path": "log.go",
      "start_line": 149,
      "end_line": 168,
      "claim": "findConflict only detects mismatches in term for the entries it is given. If the leading entry is removed beforehand, its index is never examined and cannot cause rejection."
    },
    {
      "path": "raft.go",
      "start_line": 933,
      "end_line": 965,
      "claim": "becomeLeader appends a no-op empty entry with Data: nil (line 961) and appendEntry assigns it the leader's current term and next index. This supplies the empty leading entry used by the special case."
    },
    {
      "path": "raft.go",
      "start_line": 616,
      "end_line": 659,
      "claim": "maybeSendAppend loads entries starting from pr.Next, so when Progress.Next equals the index of the leader's empty no-op entry, the MsgApp can contain both that empty entry and the subsequent non-empty proposal in one batch."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1797,
      "claim": "handleAppendEntries calls maybeAppend and, if ok, sends a non-reject MsgAppResp with Index=mlastIndex, where mlastIndex is the computed last new index. This tells the leader the entire appended range is present."
    },
    {
      "path": "raft_test.go",
      "start_line": 174,
      "end_line": 184,
      "claim": "Existing test verifies that in probe state a single MsgApp contains two entries: the leader's empty no-op entry followed by the first proposed non-empty entry, confirming the mixed batch shape that triggers the special case."
    }
  ],
  "mechanism": {
    "violated_obligation": "When a follower accepts an append, the implementation must ensure that the resulting logical log matches the leader's through the acknowledged index, and in particular must detect and truncate any existing conflicting entry before appending new entries.",
    "decisive_relation": "The special-case at log.go:116-121 removes the first entry from `check` before findConflict when that entry is empty, is at l.lastIndex(), and the next entry is non-empty. This prevents detection of a term-mismatching existing entry at the follower's current last index, allowing the follower to keep that conflicting entry while appending and acknowledging the next entry."
  },
  "causal_chain": [
    "A new leader appends an empty no-op at index N and a non-empty proposal at N+1, then sends a MsgApp to a follower whose Progress.Next is N; the batch contains both entries.",
    "The follower's maybeAppend sees a.prev match, then removes the empty entry at index N from the conflict check because check[1] is non-empty; findConflict only examines index N+1.",
    "maybeAppend appends only a.entries[1:] (the proposal at N+1), preserving the follower's old conflicting entry at index N, and returns lastnewi=N+1.",
    "handleAppendEntries publishes a successful MsgAppResp for index N+1, making the leader believe the follower's prefix through N+1 matches.",
    "Now both nodes contain the same term and payload at index N+1, but their prefixes through N+1 differ at index N (old conflicting entry vs leader's empty no-op), contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "A 3-node cluster. Leader A in term T has log prefixes matching B through N-1, has empty no-op at index N (term T, Data nil), and non-empty proposal at index N+1 (term T). Follower B has an old entry at index N with term != T and non-empty payload, and B's Progress under A has Match=N-1, Next=N. A third node is available to satisfy any quorum requirements.",
    "actions": [
      "A1: Deliver from A to B a MsgApp with Index=N-1, LogTerm=term of N-1, Entries=[empty EntryNormal at index N (term T, Data nil), EntryNormal at index N+1 (term T, Data non-empty)], Commit minimal.",
      "A2: On B, process the append and publish the resulting MsgAppResp; verify it is non-reject with Index=N+1.",
      "A3: Inspect LogicalLog(B) and LogicalLog(A) after the response completes."
    ],
    "violation": "LogicalLog(A) and LogicalLog(B) contain the same Entry(index=N+1, term=T, payload) but their logical prefixes through N+1 are not identical because index N differs (A has empty Data term T, B retains old non-empty payload with a different term).",
    "oracle": "Compare the ordered entries in the two logical prefixes from firstIndex through N+1; find a mismatch at index N while the entries at index N+1 have identical term, kind, and payload."
  },
  "uncertainties": [
    "Reachability of the exact state where follower Progress.Next equals N while follower has a divergent entry at N and leader has a mixed empty/no-op plus non-empty batch is not established by execution in this run; the existing TestProgressFlowControl confirms the mixed-batch shape, but not this exact divergent-tail setup.",
    "The special-case may have intended invariants from callers that are not fully inspected; a downstream test must confirm the path under the supported message reordering and persistence assumptions.",
    "No execution was performed; this is a code-supported mechanism hypothesis, not a confirmed defect."
  ]
}
