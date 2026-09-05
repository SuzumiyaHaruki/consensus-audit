{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "The follower append path in raftLog.maybeAppend contains a special skip of the first empty entry when the next entry is non-empty and the first entry's index equals the follower's last index. This skip bypasses the term comparison for the first entry, allowing a follower with a conflicting older term at that index to append later entries and acknowledge success through a later index. If the leader and follower later both contain the same term at that later index, their prefixes differ earlier, violating log matching.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 136,
      "claim": "maybeAppend first checks the previous entry term, then creates a check slice. If len(check)>1, the first entry has empty Data, the second has non-empty Data, and check[0].Index equals the follower's lastIndex, the first entry is removed from conflict checking. This means the first entry's term is not compared with the follower's existing entry at that index, and subsequent append logic may not replace it while still returning a successful lastnewi that includes the skipped index."
    },
    {
      "path": "log.go",
      "start_line": 138,
      "end_line": 147,
      "claim": "append delegates to unstable.truncateAndAppend with the provided entries. If those entries exclude the skipped first entry, the existing conflicting entry at the skipped index is not notified of replacement, so it remains part of LogicalLog."
    },
    {
      "path": "log_unstable.go",
      "start_line": 196,
      "end_line": 218,
      "claim": "truncateAndAppend only replaces or truncates entries starting at ents[0].Index. Entries before ents[0].Index remain unchanged. Thus if a conflicting first entry is omitted from the appended slice, it remains in the unstable log."
    },
    {
      "path": "raft.go",
      "start_line": 815,
      "end_line": 846,
      "claim": "appendEntry on the leader sets Index and Term for new entries. becomeLeader appends an empty entry (Data nil) first, and subsequent client proposals append non-empty entries, so a MsgApp can contain [empty@i, data@i+1]."
    },
    {
      "path": "raft.go",
      "start_line": 961,
      "end_line": 965,
      "claim": "becomeLeader explicitly appends an empty entry with Data nil, providing the first-entry Data empty condition."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1797,
      "claim": "handleAppendEntries calls maybeAppend and, on success, sends MsgAppResp with Index mlastIndex (the returned lastnewi). This acknowledges the skipped index even though the first entry may not have been replaced."
    }
  ],
  "mechanism": {
    "violated_obligation": "When a follower accepts a log slice, it must ensure that every entry in the accepted range matches the leader's entries, including a first entry that is empty. It must replace any conflicting entry at the same index before acknowledging a later index, to preserve log matching.",
    "decisive_relation": "In raftLog.maybeAppend, the condition `len(check) > 1 && check[0].Index == l.lastIndex() && len(check[0].Data) == 0 && len(check[1].Data) > 0` removes the first entry from `check` before findConflict. The first entry's term is therefore never compared with the follower's existing term at that index. If the follower has a different term there, the code appends only the later entries and returns lastnewi including the skipped index, while the conflicting first entry remains in the follower's logical log. The leader uses the returned lastnewi to update progress and may later consider the follower matched through the later index."
  },
  "causal_chain": [
    "Leader appends an empty no-op entry at its current term and then a non-empty client entry, producing an MsgApp with entries [empty@i, data@i+1].",
    "Follower receives the MsgApp with a matching previous entry; maybeAppend skips the empty first entry because of the Data/lastIndex condition, so its term is not checked.",
    "If the follower's existing entry at index i has a different term, findConflict only sees the entry at i+1, appends it, leaves index i unchanged, and returns success with lastnewi=i+1.",
    "The leader updates progress to i+1; later both nodes can contain an entry at index i+1 with the same term while their entries at index i differ, contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: Three-node fixed-membership Raft cluster. Leader L has empty entry e_i at index i with term T, and non-empty entry e_{i+1} at index i+1 with term T. Follower F has an entry at index i with term T' != T (e.g., from an earlier uncommitted leader), and no entry at index i+1. L and F agree on all entries before i.",
    "actions": [
      "A1: L sends MsgApp to F with Entries = [e_i (Data empty, Term T, Index i), e_{i+1} (Data non-empty, Term T, Index i+1)] and prev Index i-1, prev Term matching both logs.",
      "A2: F processes the MsgApp. The special skip in maybeAppend removes e_i from conflict checking, so F appends only e_{i+1} at index i+1 and sends MsgAppResp with Index i+1."
    ],
    "violation": "V: Leader L and follower F both have an entry at index i+1 with term T, but their entries at index i differ (L has empty entry term T; F has old entry term T'). This violates Q-LOG-2's prefix-matching requirement.",
    "oracle": "O: After the append response is processed, inspect LogicalLog(L) and LogicalLog(F). Assert that both contain an entry at index i+1 with same term T, and that the entry at index i differs in term between L and F."
  },
  "uncertainties": [
    "Reachability of the precondition (follower having a conflicting entry at the skipped index while matching the previous index) has not been demonstrated by an execution harness; it is plausible from normal Raft divergence scenarios but not executed.",
    "The scenario assumes the follower's conflicting entry at index i is in the unstable or stable logical log and that the leader's empty entry and non-empty entry are sent in the same MsgApp without intervening truncation. This ordering follows from inspected appendEntry and maybeSendAppend, but no live/non-live execution was performed.",
    "The property's 'completed states' includes accepted unstable state, but whether the append is considered completed immediately after handleAppendEntries or only after readiness persists may depend on caller obligations; inspected source uses LogicalLog of unstable entries for log state."
  ]
}
