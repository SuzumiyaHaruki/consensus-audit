{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "In raftLog.maybeAppend, a narrow exception drops the first incoming entry from conflict detection when that entry has zero-length Data and is at the follower's current last index while the next incoming entry has non-empty Data. The function then still appends the subsequent entries and acknowledges the entire slice. This can leave an older, term-mismatched empty entry in the follower's logical log while later entries match, producing a prefix divergence at a shared later entry term. Reachability under a multi-term leader sequence is not execution-confirmed.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 136,
      "claim": "maybeAppend checks a special guard at lines 116-121: if len(check)>1, check[0].Index == l.lastIndex(), len(check[0].Data)==0, and len(check[1].Data)>0, it sets check=check[1:]. It then calls findConflict(check). When check[1] is beyond lastIndex, findConflict returns check[1].Index; offset=a.prev.index+1 and ci-offset=1, so append(a.entries[ci-offset:]...) appends only a.entries[1:] and omits the first entry, while lastnewi still returns a.prev.index+len(a.entries)."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1797,
      "claim": "handleAppendEntries passes the MsgApp logSlice to raftLog.maybeAppend. On success it sends MsgAppResp Index=mlastIndex, where mlastIndex is the last index returned by maybeAppend, thereby acknowledging all entries in the slice even if the first entry was not appended due to the special guard."
    }
  ],
  "mechanism": {
    "violated_obligation": "Every entry in an accepted MsgApp slice must be conflict-checked by index and term, and any existing entry at the same index with a different entry identity must be replaced or the append must be rejected. No special case may acknowledge an entry as accepted while leaving the existing entry at that index in the follower's logical log.",
    "decisive_relation": "log.go lines 116-121 remove check[0] from findConflict input when check[0] is an empty-Data entry at the follower's current last index and check[1] is non-empty. With check[0] removed, the first remaining entry is beyond lastIndex and findConflict returns its index. Since offset=a.prev.index+1 and ci-offset=1, append(a.entries[1:]...) skips the conflicting first entry even though lastnewi includes it, allowing an older term-mismatched empty entry at index k to remain in LogicalLog while later entries k+1 onward are appended and acknowledged."
  },
  "causal_chain": [
    "A follower has an existing EntryNormal with empty Data at index k and term T1, and receives a MsgApp whose entries are [k: EntryNormal empty Data term T2, k+1: EntryNormal non-empty Data term T2].",
    "In raftLog.maybeAppend, the special empty-first-entry guard drops entry k from conflict detection, findConflict returns the new index k+1, and append(a.entries[1:]...) leaves the old term-T1 entry at k while appending the term-T2 entry at k+1; maybeAppend returns ok and the follower sends a successful MsgAppResp for index k+1.",
    "A leader or peer can hold index k with term-T2 empty Data and index k+1 with the same term-T2 non-empty Data. Both nodes now contain the same entry term at index k+1, but their logical prefixes through k+1 differ at index k, contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: fixed 3-node cluster with nodes 1,2,3. Node 2 (follower) at term 2 has committed/unstable logical log up to index k-1 with matching term, and contains at index k an EntryNormal with empty Data and term 1. Node 3 (leader) at term 2 has at index k an EntryNormal with empty Data and term 2, and at index k+1 an EntryNormal with Data \"x\" and term 2. The previous index k-1 term matches on both nodes.",
    "actions": [
      "A1: Node 3 sends MsgApp to node 2 with Index=k-1, LogTerm=matching term, Entries=[k: EntryNormal empty Data term 2, k+1: EntryNormal Data \"x\" term 2].",
      "A2: Node 2 processes handleAppendEntries; maybeAppend accepts and node 2 sends MsgAppResp Index=k+1 accepted.",
      "A3: Inspect LogicalLog of node 2 and node 3 through index k+1."
    ],
    "violation": "V: node 2 and node 3 both have the same entry term at index k+1 (term 2 EntryNormal \"x\"), but their logical prefixes through k+1 differ at index k (node 2 has term 1 empty Data, node 3 has term 2 empty Data).",
    "oracle": "O: Compare Entry(index,term,kind,payload) values for indexes from firstIndex through k+1 on node 2 and node 3. The comparison fails at index k."
  },
  "uncertainties": [
    "The required state with an old empty term-1 entry at index k and a new term-2 empty entry at the same index has not been produced by an execution harness; election-safety and message-order reachability remain to be confirmed downstream.",
    "The special guard may rely on an unstated invariant that empty entries at the follower's last index always match under valid Raft operation; inspected comments do not establish such an invariant.",
    "The source-level contradiction is static; no runtime observation was performed in this audit."
  ]
}
