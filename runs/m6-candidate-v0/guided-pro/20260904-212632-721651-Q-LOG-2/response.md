{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) contain entries with the same entry term at the same index i, then their logical prefixes through i contain identical Entry(index,term,kind,payload) values in the same order.",
  "summary": "maybeAppend has a special case that removes the first entry of an AppendEntries batch from conflict checking when that entry is an empty entry at the follower's last index and is followed by a non-empty entry. If the follower's existing entry at that index is conflicting, the append path appends only the later entry without replacing the skipped index, so two completed logical logs can later share a term at a higher index while their prefixes differ at the skipped index. The principal limitation is that the necessary follower log state and exact batched MsgApp shape are code-supported as a plausible Raft divergence scenario but were not executed in this run.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 135,
      "claim": "maybeAppend first requires only that the previous entry matches. It then special-cases a batch whose first entry is empty, whose index equals the local lastIndex, and whose second entry is non-empty by setting check=check[1:]. findConflict is run only on the remaining entries. When a conflict is found later, the code appends a.entries[ci-offset:], which excludes the skipped first entry; therefore an existing conflicting entry at that skipped index is not truncated or replaced."
    },
    {
      "path": "log_unstable.go",
      "start_line": 196,
      "end_line": 218,
      "claim": "truncateAndAppend appends from the first supplied entry index. In the relevant path the supplied entries begin at the later index, so the existing entry at the skipped index remains in the unstable log when it is already unstable, or remains in stable storage when the append is simply an extension."
    },
    {
      "path": "raft.go",
      "start_line": 933,
      "end_line": 970,
      "claim": "When a node becomes leader, becomeLeader appends an empty entry with nil Data at its current term, so a newly elected leader's log normally has an initial empty entry immediately before subsequent proposals."
    },
    {
      "path": "raft.go",
      "start_line": 616,
      "end_line": 658,
      "claim": "maybeSendAppend builds a MsgApp containing consecutive log entries from pr.Next onward, so a single MsgApp can carry the initial empty entry and the first non-empty proposal together."
    },
    {
      "path": "raft_test.go",
      "start_line": 175,
      "end_line": 184,
      "claim": "The test text confirms that the first append after leader election has two entries: the empty entry confirming the election and the first proposal, so the batched [empty, non-empty] MsgApp shape is an expected operational path."
    }
  ],
  "mechanism": {
    "violated_obligation": "When an AppendEntries message is accepted after matching the previous entry, the implementation must make the follower's logical prefix through the last new entry identical to the leader's, including replacing any conflicting entry at the first index in the batch.",
    "decisive_relation": "maybeAppend deliberately excludes the first entry from findConflict solely because it is empty, is at l.lastIndex(), and is followed by a non-empty entry, without first verifying that the existing last-index entry matches it. If the later entry conflicts, the append slice starts at that later index, so the skipped existing entry survives; yet maybeAppend returns success for the whole batch. This can create two logs that both contain a shared later-term entry while their prefixes differ at the skipped index."
  },
  "causal_chain": [
    "A newly elected leader appends an empty no-op entry at index i and a client proposal at index i+1, then sends one MsgApp carrying both entries.",
    "A follower has a matching log through i-1 but an old conflicting entry at index i, so its lastIndex is i.",
    "In maybeAppend, the first empty entry at index i is removed from the conflict check; conflict detection begins at i+1 and finds no existing entry there.",
    "The code appends only the i+1 entry and returns success, leaving the follower's old conflicting entry at index i intact.",
    "Leader and follower now both contain an entry at index i+1 with the same term, but their prefixes through i+1 differ at index i, contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: Three fixed voters {1,2,3}. Node 1 is leader at term T with log prefix through i-1 common to node 2. Node 1's log has an empty EntryNormal at index i term T and a non-empty EntryNormal \"prop\" at index i+1 term T. Node 2's last log index is i and contains an uncommitted non-empty EntryNormal \"old\" with a term older than T; node 2 matches node 1 at i-1.",
    "actions": [
      "A1: Deliver a MsgApp from node 1 to node 2 with Index=i-1, LogTerm=term(i-1), Entries=[empty EntryNormal at i term T, EntryNormal \"prop\" at i+1 term T].",
      "A2: Let node 2 process handleAppendEntries and complete the resulting append; no crash or storage loss is required for the logical-log mismatch."
    ],
    "violation": "V: node 1 and node 2 both contain a log entry at index i+1 with term T, but their logical prefixes through i+1 differ: node 1 has the empty entry at i whereas node 2 retains EntryNormal \"old\" at i.",
    "oracle": "O: After the append completes, inspect LogicalLog(1) and LogicalLog(2). For index i+1 both entries have term T, but a prefix comparison through i+1 shows the entry at index i differs in payload/kind, so Q-LOG-2 is negated."
  },
  "uncertainties": [
    "The existence of a reachable state where a follower has a conflicting uncommitted entry at the leader's first no-op index and also matches the preceding index is not established by executed source in this audit; it is a plausible Raft divergence scenario, not an execution-confirmed precondition.",
    "The audit did not execute the precise batched MsgApp through an integration harness, so the downstream reachability and completion behavior remain to be validated by the test construction.",
    "It was not established that another invariant of the leader's append generation cannot prevent the exact [empty, non-empty] batch from being sent to a follower whose last index is the conflict index."
  ]
}
