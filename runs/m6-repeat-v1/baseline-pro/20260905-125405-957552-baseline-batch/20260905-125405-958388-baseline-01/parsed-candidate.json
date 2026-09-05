{
  "status": "candidate_found",
  "property_id": null,
  "property_statement": "For every entry e applied by a node n at log index i, after n crashes and restarts with the same identity, LogicalLog(n) must contain e at index i; equivalently, an entry must not be handed to the application as committed unless its local log copy is durable across the crash-recovery fault model.",
  "summary": "In synchronous storage mode RawNode.Ready computes CommittedEntries with allowUnstable=true, so it may include committed entries that have not yet been durably appended to the local log. If the application acknowledges applying those entries before persisting the corresponding Ready.Entries, a crash can leave Applied(n,i,e) completed while the durable logical log no longer contains e after restart. The principal limitation is that the Ready contract's application ordering is not enforced by the inspected code, so the scenario depends on the application relying on the documented 'previously appended to stable storage' guarantee.",
  "source_evidence": [
    {
      "path": "rawnode.go",
      "start_line": 141,
      "end_line": 147,
      "claim": "Ready construction passes rn.applyUnstableEntries() as the allowUnstable argument to r.raftLog.nextCommittedEnts, so the returned CommittedEntries depend on whether unstable entries are allowed."
    },
    {
      "path": "rawnode.go",
      "start_line": 445,
      "end_line": 450,
      "claim": "applyUnstableEntries returns true when AsyncStorageWrites is false, i.e. normal synchronous storage mode permits applying unstable committed entries."
    },
    {
      "path": "log.go",
      "start_line": 225,
      "end_line": 249,
      "claim": "nextCommittedEnts computes the upper bound as l.maxAppliableIndex(allowUnstable) and slices entries from applying+1 to that bound, so it can return entries above the stable log boundary when allowUnstable is true."
    },
    {
      "path": "log.go",
      "start_line": 268,
      "end_line": 278,
      "claim": "maxAppliableIndex caps at l.unstable.offset-1 only when allowUnstable is false; when allowUnstable is true it returns l.committed, even if l.committed is beyond the last durably stored index."
    },
    {
      "path": "node.go",
      "start_line": 89,
      "end_line": 96,
      "claim": "The Ready contract documents CommittedEntries as entries that 'have previously been appended to stable storage', conflicting with the synchronous-mode allowUnstable=true behavior."
    }
  ],
  "mechanism": {
    "violated_obligation": "In synchronous storage mode, RawNode.Ready must not present a log entry as a CommittedEntry unless that entry has already been durably appended to the node's stable storage.",
    "decisive_relation": "Because applyUnstableEntries() returns true when AsyncStorageWrites is false, nextCommittedEnts uses maxAppliableIndex(true), which caps the committable slice at l.committed instead of at l.unstable.offset-1. Thus an entry in the unstable part of the log can be returned for application while its local persistence is still pending."
  },
  "causal_chain": [
    "A follower in synchronous storage mode receives a MsgApp carrying entry e at index i and appends it to the unstable log; leader commit advances r.raftLog.committed to i.",
    "RawNode.Ready() is called with AsyncStorageWrites=false, so CommittedEntries is computed with allowUnstable=true and includes e even though e is not yet in local stable storage.",
    "The application applies and acknowledges e from CommittedEntries, completing Applied(n,i,e) before the corresponding Ready.Entries has been persisted.",
    "The node crashes and restarts from durable storage. The unstable append of e is lost, so LogicalLog(n) no longer contains e at i, despite the already-completed Applied(n,i,e) event."
  ],
  "test_sketch": {
    "precondition": "P: 3-node fixed voter set; node n is a follower with AsyncStorageWrites=false; leader has committed entry e at index i and sent it to n; n has appended e only to its unstable log, and r.raftLog.committed has advanced to i.",
    "actions": [
      "A1: Call RawNode.Ready on n and obtain a Ready containing Entries=[e] and CommittedEntries=[e] (or CommittedEntries including e). Apply/acknowledge the CommittedEntries to n's state machine without yet persisting the Ready.Entries.",
      "A2: Crash n before its storage layer durably persists the Ready.Entries; restart n from its durable Storage and provide the persisted applied index i to the new instance."
    ],
    "violation": "V: After restart, n's durable raft log/logical log does not contain e at index i while Applied(n,i,e) has already completed; the same index can later be bound to a different entry or be re-applied, violating the derived log/apply safety property.",
    "oracle": "O: Inspect n's recovered raftLog and Storage; assert that LogContains(n,i,e) is false, while the application's acknowledged apply record still shows e was applied at index i before the crash."
  },
  "uncertainties": [
    "The scenario assumes the application processes Ready.CommittedEntries before persisting Ready.Entries based on the documented Ready contract that CommittedEntries have previously been appended to stable storage; if an inspected caller obligation forbids that ordering, the reachable violation is reduced to a documentation/contract inconsistency rather than a confirmed consensus safety break.",
    "The test requires the application/applied index to be durable so that the pre-crash Applied event remains observable after restart; this persistence is outside the library and was not inspected."
  ]
}
