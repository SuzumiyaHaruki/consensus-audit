{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "raftLog.maybeAppend has a special-case conflict skip for an incoming empty first entry followed by a nonempty entry when the first entry is at the receiver's current last index. If that first entry conflicts by term with the receiver's existing entry, the conflict is not detected, so the receiver keeps its old entry at that index while still acking the full append range. This can make a leader believe the follower's log matches through the acknowledged index even though the follower's prefix differs, violating Q-LOG-2.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 105,
      "end_line": 136,
      "claim": "maybeAppend first checks only prev term. Then, when the incoming entries are at least two, the first has the receiver's current last index, empty Data, and the second has nonempty Data, it removes the first entry before running findConflict (lines 116-121). Because findConflict only tests term matches (line 161), a term conflict in that skipped first entry is ignored. It then computes a conflict from the remaining entries; for a second entry beyond lastIndex this is that second index, so it appends only from the second entry onward (line 132) and still returns ok=true with lastnewi covering all original entries (lines 114, 135). This is executable behavior establishing the decisive skip."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1798,
      "claim": "handleAppendEntries passes the MsgApp slice to maybeAppend and, when maybeAppend returns ok=true, immediately sends MsgAppResp Index=mlastIndex, which is the last index of the original entries, even though maybeAppend may not have appended the skipped first entry. This lets the sender treat the full range as appended by the follower."
    },
    {
      "path": "raft.go",
      "start_line": 1510,
      "end_line": 1524,
      "claim": "On receiving a non-rejected MsgAppResp, the leader conditionally calls pr.MaybeUpdate(m.Index), advancing the tracked Match for that follower. Combined with the ack described above, the leader can advance Match through an index whose entry the follower did not actually replace and whose term differs."
    },
    {
      "path": "tracker/progress.go",
      "start_line": 205,
      "end_line": 213,
      "claim": "MaybeUpdate accepts the acked index if it is greater than the current Match and sets Progress.Match to that index. This is the leader-side state transition that may incorrectly record log-prefix equality through the acked range."
    }
  ],
  "mechanism": {
    "violated_obligation": "The implementation must ensure that a successful append acknowledgement implies the follower's logical log prefix through the acknowledged index is identical to the leader's prefix through that index, or reject at the first conflicting entry.",
    "decisive_relation": "In raftLog.maybeAppend, the conditional at lines 116-121 drops the first incoming entry from conflict detection when that entry has empty Data, is at the receiver's current lastIndex, and is followed by a nonempty entry. If that dropped first entry has a different term from the receiver's existing entry at the same index, its conflict is not recognized; findConflict then identifies only the following index as the append point and appends from there. maybeAppend still returns ok=true with lastnewi covering the original first entry, and handleAppendEntries sends an ack for that full range. As a result, the leader may mark a conflicting index as matched while the follower retains its old entry at that index, breaking the required identical prefix."
  },
  "causal_chain": [
    "A leader sends a MsgApp whose entries slice contains an empty-data entry E_L at index L followed by a nonempty entry E_{L+1} at index L+1, and the receiving follower already has a different-term entry at index L.",
    "handleAppendEntries calls raftLog.maybeAppend; the special condition skips conflict checking for E_L, so the term conflict at L is not detected.",
    "findConflict sees E_{L+1} beyond the follower's lastIndex and treats index L+1 as the append point, causing only E_{L+1} to be appended and leaving the follower's old E_L in place.",
    "maybeAppend returns lastnewi=L+1 and true, so the follower publishes MsgAppResp Index=L+1; the leader's leader-side MsgAppResp handling calls MaybeUpdate, advancing Match through L+1.",
    "The completed LogicalLogs now have the same term T_L at index L+1, but their prefixes through L+1 differ at index L (leader has empty-data T_L, follower has old different-term/payload entry), contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: A fixed-membership Raft cluster. Leader A and follower B agree through index L-1. A has appended an empty-data entry at index L and a nonempty entry at index L+1, and B has a conflicting nonempty entry at index L with term T_f. A sends B a single MsgApp with prev=(L-1,term common), entries=[E_L(term T_L, empty), E_{L+1}(term T_L, nonempty)]; both entries fit in A's outgoing MsgApp under current Progress state.",
    "actions": [
      "A1: Deliver that MsgApp to B.",
      "A2: B executes handleAppendEntries; maybeAppend skips conflict detection for E_L and appends only E_{L+1}.",
      "A3: B sends MsgAppResp Index=L+1 to A.",
      "A4: A processes that MsgAppResp and advances B's Progress.Match to L+1."
    ],
    "violation": "V: In the resulting completed LogicalLogs of A and B, both contain an entry at index L+1 with term T_L, but their prefixes through L+1 differ at index L: A has Entry(L,T_L,empty), B has Entry(L,T_f,nonempty).",
    "oracle": "O: Query the logical log entries for A and B through index L+1. Assert that the two prefixes are byte-for-byte identical in Entry(index,term,kind,payload); the test observes A=(..., Index L term T_L Data empty, Index L+1 term T_L Data X) and B=(..., Index L term T_f Data Y, Index L+1 term T_L Data X), disproving identical prefixes under the same (L+1,T_L) entry."
  },
  "uncertainties": [
    "Reachability of a single MsgApp containing both an empty empty/leader no-op entry at its first index and a following nonempty entry was not established by the inspected normal scheduling paths; in the common path new leaders broadcast only the empty entry first and send later proposals separately.",
    "It may require a client-proposed empty-data entry followed quickly by a nonempty proposal, or a specific Progress/MaxSizePerMsg configuration for them to be batched into one MsgApp.",
    "The scenario may depend on pre-existing divergence at index L; Q-LOG-2 is a completed-state property, so the receiver and sender must reach those completed LogicalLog states as described.",
    "No execution was performed; downstream construction must confirm the batch path and the exact Data/non-empty conditions."
  ]
}
