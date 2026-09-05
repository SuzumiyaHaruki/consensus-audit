{
  "status": "candidate_found",
  "property_id": "Q-LOG-2",
  "property_statement": "For any completed states of nodes a and b, if LogicalLog(a) and LogicalLog(b) both contain entries with the same term at the same index i, then for every index <= i the two logical prefixes contain identical Entry(index, term, kind, payload) values in the same order.",
  "summary": "The follower append path in raftLog.maybeAppend contains a special case that removes the first received entry from the conflict scan whenever that entry is empty (Data length 0), its index equals the follower's current last index, and it is followed by a non-empty entry. This can preserve a conflicting uncommitted follower entry at that first index while appending the later leader entry, so the two logs can thereafter contain the later entry with the same (index, term) but with divergent prefixes. Reachability is supported by ordinary partition/leader-change histories, though no executable harness was available in this run.",
  "source_evidence": [
    {
      "path": "log.go",
      "start_line": 107,
      "end_line": 136,
      "claim": "maybeAppend checks only a.prev against the local log, then computes conflict over `check := a.entries`. If `len(check) > 1`, `check[0].Index == l.lastIndex()`, `len(check[0].Data) == 0`, and `len(check[1].Data) > 0`, it drops check[0] from the conflict scan before calling findConflict. A conflict at the follower's tail index is therefore invisible, and only later entries are passed to `append`."
    },
    {
      "path": "log.go",
      "start_line": 149,
      "end_line": 172,
      "claim": "findConflict reports the first received index whose term does not match the local log. By excluding the leading empty entry from this scan, maybeAppend makes a term mismatch at that index unreported and proceeds as though the suffix starts at a matching or new log position."
    },
    {
      "path": "log.go",
      "start_line": 138,
      "end_line": 147,
      "claim": "append forwards only the supplied entries to `unstable.truncateAndAppend`, so when maybeAppend calls append with `a.entries[ci-offset:]` rather than the full incoming slice, the conflicting entries before that truncation point remain in the logical log."
    },
    {
      "path": "log_unstable.go",
      "start_line": 196,
      "end_line": 218,
      "claim": "truncateAndAppend truncates only from the first received entry's index (`fromIndex`). If the divergent tail entry is below fromIndex (for example in stable storage, or already in unstable before fromIndex), it is preserved while the new suffix is appended, producing a mixed-term log prefix."
    },
    {
      "path": "raft.go",
      "start_line": 933,
      "end_line": 970,
      "claim": "A newly elected leader appends `pb.Entry{Data: nil}` as its empty leadership no-op and then a normal proposal assigned the next index receives non-empty Data. This establishes the exact two-entry shape used by the maybeAppend special case: empty first entry immediately followed by a non-empty entry."
    },
    {
      "path": "raft.go",
      "start_line": 616,
      "end_line": 660,
      "claim": "maybeSendAppend builds MsgApp with prevIndex=pr.Next-1 and entries from raftLog entries at pr.Next. For a peer whose progress was reset before the new leader appended its no-op, this can send the empty no-op and the immediately following proposal together, with the empty entry's index equal to the lagging follower's last index."
    }
  ],
  "mechanism": {
    "violated_obligation": "Before accepting a leader entry at index i (and later acknowledging it), the follower must delete or replace every locally stored entry that conflicts with the leader's received entries at earlier indexes; otherwise a later same-(index,term) entry can be stored above a divergent prefix, violating Log Matching.",
    "decisive_relation": "In maybeAppend, the special guard `len(check) > 1 && check[0].Index == l.lastIndex() && len(check[0].Data) == 0 && len(check[1].Data) > 0` reassigns `check = check[1:]`. A divergent follower tail at check[0].Index is thereby excluded from findConflict, and findConflict returns the next new index (ci > committed), causing `append(a.entries[ci-offset:]...)` to leave the old divergent empty entry in place while installing the follower's next entry with the leader's term."
  },
  "causal_chain": [
    "While partitioned, node 1 was leader in term t and durably retains its own empty no-op at index h+1, term t, so its logical log ends at h+1; nodes 2 and 3 continue at committed prefix h.",
    "Node 2 wins term t2 > t with nodes 2 and 3, appends its empty no-op at h+1 (term t2) and a non-empty proposal at h+2 (term t2), then sends node 1 an MsgApp anchored at h carrying entries [h+1 empty t2, h+2 payload t2].",
    "Node 1's handleAppendEntries calls maybeAppend; because check[0].Index == h+1 == node 1's lastIndex, check[0] is empty, and check[1] is non-empty, the conflict scan skips check[0] and only reports h+2, so node 1 keeps its term-t entry at h+1 and appends term-t2 entry h+2.",
    "Node 1 and node 2 now both contain entry (index=h+2, term=t2, same payload), but their prefixes through h+2 differ at h+1 (term t vs term t2), contradicting Q-LOG-2."
  ],
  "test_sketch": {
    "precondition": "P: fixed voters {1,2,3}. Nodes 1 and 2 share a committed prefix through index h. Node 1 was previously a partitioned-leader in term t and has an uncommitted empty no-op at index h+1 with term t, making its last index h+1. Node 2 is leader in term t2 > t, has appended its empty no-op at h+1 with term t2 and a normal entry with payload `p` at h+2, and has progress for node 1 with Next set before those appends (e.g. after a node-2 campaign through a majority of 2 and 3).",
    "actions": [
      "A1: Leader node 2 sends MsgApp to node 1 with Index=h, LogTerm=Term(entry h), and Entries=[{Index:h+1, Term:t2, Data:nil}, {Index:h+2, Term:t2, Data:[\"p\"]}], Commit set to the leader's committed index h.",
      "A2: Node 1's Step dispatches MsgApp; handleAppendEntries / maybeAppend executes the first-entry skip, findConflict returns h+2, and `append` and `unstable.truncateAndAppend` add only the h+2 entry while preserving node 1's existing h+1 term-t empty entry."
    ],
    "violation": "V: Both node 1 and node 2 now contain an entry at h+2 with term t2 and payload `p`, but node 1's log at h+1 is the term-t empty entry while node 2's log at h+1 is the term-t2 empty entry; the prefixes through h+2 are not identical.",
    "oracle": "O: Read each node's logical-log slice through h+2 (including stable storage and unstable entries; e.g. raftLog.entries(firstIndex, h+3)). Assert that the two slices are identical. They are not: slices agree at h+2 in (term, kind, payload) but differ at h+1, so Q-LOG-2 is false."
  },
  "uncertainties": [
    "No executable raft test harness was available in this run, so the scenario's message ordering was reasoned statically rather than demonstrated by test execution.",
    "The scenario requires that node 1's conflicting empty h+1 entry survives until node 2's append arrives (or remains in unstable memory without a prior overwrite); a partitioned old leader satisfying this is consistent with the fault model but depends on caller-specified storage and network behavior.",
    "The intended rationale of the maybeAppend first-entry skip is not documented in the inspected source, so a downstream invariant (not present in the inspected executable code) might be assumed to prevent conflicts at that leading empty entry; no such guard was found."
  ]
}
