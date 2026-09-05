{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "The follower append-acceptance path in log.go's maybeAppend has a special case that drops an empty first MsgApp entry from conflict detection whenever that entry sits at the follower's current last index and the next entry is non-empty, without checking the first entry's term. If the follower still holds a conflicting entry at that index when a leader retransmits [no-op@X, client@X+1], the follower keeps its old entry at X, appends the leader's client entry at X+1, and acks X+1. Leader and follower then share term T at index X+1 but disagree at index X, contradicting Q-LOG-2. Reachability depends on a message-loss/reordering interleaving, which is consistent with the inspected send/receive paths but not executed here.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 136,
      "claim": "maybeAppend first checks only a.prev via matchTerm. It then conditionally sets check=check[1:] when check[0].Index==l.lastIndex(), check[0].Data is empty, and check[1].Data is non-empty. This removes the empty first entry from findConflict without comparing its term to the follower's existing entry. The subsequent l.append(a.entries[ci-offset:]...) skips that first entry, so the follower retains its existing entry at that index."
    },
    {
      "path": "log.go",
      "start_line": 149,
      "end_line": 172,
      "claim": "findConflict returns the absolute index of the first entry whose (index,term) does not matchTerm; for an entry beyond lastIndex it returns that index without truncating the existing tail. With check[0] removed, a two-entry [empty@X, nonempty@X+1] slice yields ci=X+1."
    },
    {
      "path": "log.go",
      "start_line": 452,
      "end_line": 458,
      "claim": "matchTerm only verifies term equality at a single index and returns false for unavailable terms, so the skipped empty first entry's term is never checked against the follower's existing entry at that index."
    },
    {
      "path": "raft.go",
      "start_line": 616,
      "end_line": 660,
      "claim": "maybeSendAppend constructs MsgApp with prevIndex=pr.Next-1 and Entries=r.raftLog.entries(pr.Next, r.maxMsgSize). When pr.Next==X and the leader's log contains both an empty entry at X and a client entry at X+1, the produced MsgApp carries both entries."
    },
    {
      "path": "raft.go",
      "start_line": 815,
      "end_line": 846,
      "claim": "appendEntry sets every proposed entry's Term to r.Term and assigns consecutive indices after lastIndex; a leader's client proposal therefore gets the same term as its own no-op entry and follows it at the next index."
    },
    {
      "path": "raft.go",
      "start_line": 933,
      "end_line": 970,
      "claim": "becomeLeader appends a pb.Entry with nil Data (an empty no-op) at lastIndex+1 in the new leader's current term, producing the empty first entry needed for the special case."
    },
    {
      "path": "raft.go",
      "start_line": 1286,
      "end_line": 1345,
      "claim": "A MsgProp on the leader appends the proposed entries via appendEntry and then calls bcastAppend, so a non-empty client entry can be appended immediately after the no-op and sent to followers."
    },
    {
      "path": "raft.go",
      "start_line": 1691,
      "end_line": 1701,
      "claim": "On winning an election the node calls becomeLeader (appending the no-op) and then bcastAppend, sending the initial MsgApp for the no-op to peers."
    },
    {
      "path": "raft.go",
      "start_line": 1786,
      "end_line": 1828,
      "claim": "handleAppendEntries calls maybeAppend on the received MsgApp and, on success, publishes MsgAppResp Index=lastnewi, which the leader uses to advance this follower's match index through X+1."
    }
  ],
  "mechanism": {
    "violated_obligation": "Before acknowledging appended entries, a follower must ensure its logical log matches the leader's log for every index in the acknowledged prefix; specifically, when a MsgApp carries an entry whose index already exists in the follower's log, the follower must verify that entry's term and replace any conflicting entry, so that once leader and follower share an entry term at some index, all prior entries are identical.",
    "decisive_relation": "log.go lines 116-121 remove check[0] from conflict detection solely because it is empty, sits at l.lastIndex(), and is followed by a non-empty entry. The removed entry's term is never compared to the follower's existing entry. findConflict then returns the next index X+1, and line 132 appends a.entries[ci-offset:] = a.entries[1:], so a conflicting existing entry at the follower's last index X is preserved while the entry at X+1 is accepted and acknowledged."
  },
  "causal_chain": [
    "Follower F has a log prefix matching leader L through index X-1 but retains an extra uncommitted conflicting entry at index X from an older term T_old.",
    "L wins election at term T>T_old and appends an empty no-op at index X; L's Progress.Next for F is X, and L's first single-entry MsgApp for the no-op is delayed or dropped.",
    "Before F acknowledges the no-op, L appends a non-empty client entry at X+1 and sends MsgApp(prevIndex=X-1, Entries=[empty@X term T, client@X+1 term T]) to F.",
    "F's maybeAppend passes the prevIndex match, then the special case at log.go:116-121 removes the empty entry at X from conflict detection; findConflict returns X+1 and append retains F's old entry at X while adding client@X+1.",
    "F publishes MsgAppResp Index=X+1, so L records F as matched through X+1; both nodes now have term T at index X+1, but their prefixes differ at index X, violating Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: 3-node fixed-membership Raft cluster {1,2,3}. Node 1 (follower) and nodes 2,3 share entries [1..X-1]. Node 1 additionally has an uncommitted entry at index X with term T_old (T_old < T) and a non-empty payload, and is committed through X-1. Arrange node 2 to win an election at term T with votes from itself and node 3, so its no-op lands at index X as an empty entry of term T. Ensure node 1's first single-entry MsgApp carrying only the no-op is dropped or delayed.",
    "actions": [
      "A1: Deliver a non-empty client proposal to leader node 2; node 2 appends it at index X+1 with term T and broadcasts MsgApp.",
      "A2: Deliver to node 1 the MsgApp with Index=X-1, LogTerm=term(X-1), Entries=[Entry{Index:X, Term:T, Data:empty}, Entry{Index:X+1, Term:T, Data:\"v\"}] (the first single-entry no-op MsgApp remains undelivered).",
      "A3: Node 1 processes handleAppendEntries/maybeAppend and publishes MsgAppResp Index=X+1; deliver that ack to node 2."
    ],
    "violation": "V: Node 1 retains its old entry at index X (term T_old, non-empty) while appending the leader's entry at X+1 (term T, \"v\"); node 2 has (X, term T, empty) and (X+1, term T, \"v\"). Both nodes now contain an entry with term T at index X+1, but their logical prefixes through X+1 differ at index X.",
    "oracle": "O: After node 2 advances node 1's match index to X+1, inspect the logical logs of nodes 1 and 2 over indices 1..X+1. Assert that at index X+1 both entries have term T and identical payload, yet the entries at index X differ in term or payload; this negates Q-LOG-2."
  },
  "uncertainties": [
    "The scenario requires a specific message interleaving: node 1's first single-entry MsgApp (no-op only) is dropped or delayed while the later two-entry MsgApp is delivered; this follows from inspected send/receive paths but was not executed.",
    "It assumes node 1 can have an uncommitted conflicting entry at index X while still matching the leader through X-1, and that the rest of the cluster elects node 2 without node 1's vote; this is consistent with Raft election rules but not executed.",
    "The violation is observed at the logical-log state immediately after node 1's append/ack; if the delayed single-entry no-op MsgApp is later delivered, it would truncate and repair index X, but the already-completed conflicting state is the historical fact used by Q-LOG-2."
  ]
}
