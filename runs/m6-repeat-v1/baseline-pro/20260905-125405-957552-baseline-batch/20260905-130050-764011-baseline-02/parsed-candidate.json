{
  "status": "candidate_found",
  "property_id": null,
  "property_statement": "Raft Log Matching: if a follower accepts an append that covers index i+1, it must also ensure that its log at index i matches the leader's anchored log entry at every prior index. In particular, an entry that conflicts with the leader's empty entry at index i must be replaced before any later entry at i+1 is accepted.",
  "summary": "In raftLog.maybeAppend there is a special-case path that removes a leading empty entry from conflict detection when it sits at the receiver's current last index and is followed by a non-empty entry. If that empty entry conflicts with the receiver's existing entry, the conflict is not detected, the later non-empty entry is appended, and the receiver still returns an acknowledgement covering both indexes. This can let a follower retain a conflicting prefix while reporting a higher match index, violating log matching and potentially leader completeness.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 134,
      "claim": "maybeAppend first verifies a.prev, then conditionally removes the first append entry from the conflict-check slice when it is an empty entry at the receiver's current last index and the next entry is non-empty. The remaining findConflict and append operate on the shortened check slice, so a conflicting empty entry is not replaced, while lastnewi still covers the full original entry range and commitTo can advance past it."
    },
    {
      "path": "log.go",
      "start_line": 149,
      "end_line": 171,
      "claim": "findConflict returns the index of the first entry whose term does not match the local log. Skipping the leading entry in maybeAppend means a mismatch at that index is never returned and the append starts at the following index."
    }
  ],
  "mechanism": {
    "violated_obligation": "A follower must detect and truncate log conflicts from the first conflicting index before accepting any subsequent entries from an AppendEntries message.",
    "decisive_relation": "The condition at log.go:116-120 drops a leading empty entry from check when check[0].Index == l.lastIndex(), len(check[0].Data)==0, and len(check[1].Data)>0. If that leading empty entry has a different term than the receiver's existing entry at the same index, findConflict is called on a slice starting at index+1, so the conflict is invisible. l.append therefore appends only the later non-empty entry, but the returned lastnewi and eventual MsgAppResp index cover the omitted conflicting entry as if it had been replaced."
  },
  "causal_chain": [
    "Leader sends an MsgApp whose prev entry matches, with entries [empty entry at index k, non-empty entry at index k+1], while the follower has an existing entry at index k with a different term.",
    "maybeAppend drops the leading empty entry from conflict checking because it is at the follower's current last index and is empty, so the term mismatch at k is not detected.",
    "Follower appends only the entry at k+1 and returns lastnewi = k+1, then sends MsgAppResp Index=k+1 to the leader.",
    "Leader records Match=k+1, potentially commits entries through k+1, while the follower's log contains a stale term at k followed by the new term at k+1.",
    "If the follower later becomes leader, its log at k differs from the majority's committed entry at k, so it can overwrite a committed prefix, violating Raft's Log Matching / Leader Completeness guarantee."
  ],
  "test_sketch": {
    "precondition": "P: three-node fixed voter cluster {A,B,C}. A is leader in term 2. Nodes A and B have identical log prefix through k-1, then term-2 empty entry at index k and term-2 non-empty entry 'new' at index k+1. C's log has matching prefix through k-1, but a stale uncommitted term-1 entry 'old' at index k and no entry at k+1. B is temporarily partitioned or delayed so A can replicate to C.",
    "actions": [
      "A1: A sends one MsgApp to C with Index=k-1, LogTerm=term(k-1), Entries=[Entry{Term:2, Index:k, Data:nil}, Entry{Term:2, Index:k+1, Data:\"new\"}].",
      "A2: C handles the MsgApp, emits a Ready containing the unstable appended entries, and processes it durably.",
      "A3: C publishes MsgAppResp Index=k+1 to A."
    ],
    "violation": "V: C's durable LogicalLog contains Entry(term=1,index=k,data=\"old\") and Entry(term=2,index=k+1,data=\"new\"), while its MsgAppResp Index=k+1 falsely implies that indices through k+1 match the leader's log. A can advance its commit index using C's ack.",
    "oracle": "O: externally inspect C's durable raft log after A's append and before any further replication; observe that the entry at index k is still term 1 while the entry at index k+1 is term 2. Equivalently, isolate C with A and B stopped/crashed, let C campaign and become leader, then observe that the term-1 entry at index k is replicated over the committed term-2 empty entry on a correct node."
  },
  "uncertainties": [
    "Reachability of the exact single MsgApp containing a leading empty entry and a following non-empty entry when the follower has a conflicting entry at that index was not demonstrated by an executed integration test.",
    "The scenario also assumes the conflicting entry at k is uncommitted and that the follower's log last index equals k at the time of the append; this condition is code-supported but not dynamically verified here.",
    "No execution was available to confirm the downstream election and committed-prefix overwrite; the candidate is a static code-supported mechanism."
  ]
}
