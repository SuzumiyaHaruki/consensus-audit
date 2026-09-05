{
  "status": "candidate_found",
  "property_id": null,
  "property_statement": "A node must durably persist its currentTerm and votedFor before publishing any formal vote request (MsgVote) for that term.",
  "summary": "The implementation emits MsgVote requests through the ordinary Ready.Messages path, not the deferred msgsAfterAppend path, so a candidate can publish a RequestVote before its HardState append is durable. This is a concrete persistence-ordering mechanism with uncertain higher-level election-safety consequences.",
  "source_evidence": [
    {
      "path": "raft.go",
      "start_line": 1039,
      "end_line": 1072,
      "claim": "In campaign(), becoming a candidate sends MsgVote to all remote voters via r.send, while the self-vote response is queued separately through r.send as a vote response type. The remote MsgVote emission itself is not conditioned on the new HardState being durable."
    },
    {
      "path": "raft.go",
      "start_line": 512,
      "end_line": 598,
      "claim": "r.send() only defers MsgAppResp, MsgVoteResp, and MsgPreVoteResp by appending them to msgsAfterAppend. MsgVote requests are not in that deferred set, so they are appended to r.msgs for immediate exposure in the next Ready.",
      "claim_path": "raft.go",
      "claim_start_line": 512,
      "claim_end_line": 598
    },
    {
      "path": "rawnode.go",
      "start_line": 133,
      "end_line": 186,
      "claim": "RawNode.Ready() returns r.msgs as Ready.Messages. In either storage mode, MsgVote messages appear in Ready.Messages without an enforced dependency on the HardState append completing. In async mode the library creates a separate MsgStorageAppend for HardState; r.msgs are still returned alongside it, so the caller can publish MsgVote before durable persistence."
    }
  ],
  "mechanism": {
    "violated_obligation": "Before publishing a MsgVote for a new term, the implementation should defer publication until the corresponding currentTerm and self-vote are durably persisted (as it already does for MsgVoteResp).",
    "decisive_relation": "MsgVote is routed to r.msgs rather than msgsAfterAppend, while HardState is emitted separately in Ready. Ready.Messages and the storage append are not ordered by the library, so MsgVote publication can precede durable currentTerm/self-vote; a crash in this window discards the new term/vote after remote peers may have acted on the request."
  },
  "causal_chain": [
    "A follower times out and calls campaign(); becomeCandidate() increments Term and sets Vote in memory, then campaign() emits MsgVote to remote voters through r.send.",
    "RawNode.Ready() places those MsgVote messages in Ready.Messages alongside a new HardState; in async mode the storage append is pending and may not have completed when the caller transmits Ready.Messages.",
    "If the node crashes after MsgVote publication but before the HardState append is durable, restart restores the old durable Term/Vote, losing the term-bearing action's persisted basis and potentially allowing another vote/candidacy in the same term."
  ],
  "test_sketch": {
    "precondition": "P: 3-node fixed configuration, PreVote=false, AsyncStorageWrites=true. Node A is initialized as a follower and forced to campaign (timeout or API Campaign). The caller can observe Ready and control completion of MsgStorageAppend acknowledgments.",
    "actions": [
      "A1: Obtain A's Ready that contains the new HardState (Term and Vote) and MsgVote messages for peers.",
      "A2: Deliver one MsgVote from that Ready to peer B while withholding/delaying A's MsgStorageAppend acknowledgment so A's HardState has not yet been durably persisted.",
      "A3: Observe publication at B and absence of a durability acknowledgment at A."
    ],
    "violation": "V: A MsgVote request is published to B before A's currentTerm/self-vote append has completed durably.",
    "oracle": "O: At the moment B receives MsgVote, assert that A has not yet processed a successful MsgStorageAppend response for the Ready that carried the new HardState (or instrument the storage thread to record no durable write has completed)."
  },
  "uncertainties": [
    "Whether this interaction actually yields two leaders in the same term or other Raft safety violation is not established; the self-vote is not counted until durable, and majority intersections may still prevent simultaneous leaders.",
    "The caller may be expected by the Ready/async storage contract to order network message transmission after durable storage; the library-commented obligation may place this ordering burden on the caller.",
    "Reachability requires a crash precisely after message publication and before local HardState durability, and depends on host scheduling/storage behavior outside the inspected library."
  ]
}
