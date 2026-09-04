# Raft Event and Completion Semantics

These are protocol-level events, not implementation mappings. The auditor must locate and justify each event's actual completion point in the target code.

## Conventions

- An intention, queued operation, or partially executed handler is not a completed event.
- A message is **published** when it leaves the sender's controlled boundary and can affect another node, regardless of later delivery.
- A value is **durable** only when the storage contract guarantees it survives the crash-recovery fault model.
- Completed events remain historical facts after later state changes.

## Term

`DurableTerm(n,t)` completes when node `n` durably stores `currentTerm=t`.

`ActsInTerm(n,t,a)` completes when `n` makes protocol action `a` effective while treating `t` as its current term, such as publishing a term-bearing message or completing a term-dependent role transition. Decoding or rejecting a stale message is not such an action.

## Vote and election

`VoteGranted(n,t,c)` completes when `n`'s affirmative formal vote for candidate `c` in term `t` becomes eligible to affect an election:

- for a remote candidate, when the affirmative response is published from `n`;
- for a self-vote, when the implementation allows it to enter `n`'s election tally.

The event does not assume prior persistence; verifying crash-safe ordering is part of the audit. A vote lost before publication or self-counting is not completed. PreVote probes are not formal votes.

`ElectionWon(c,t,C)` completes when the implementation's election logic declares `c` the winner for term `t` under voter set `C`, based on the formal votes it accepted, and `c` completes its leader transition. The event does not assume that the accepted votes form a valid `Majority(C)`; verifying the implemented quorum is part of the audit. A leader-state observation without the corresponding election decision and vote evidence is insufficient.

## Log and leadership

`Entry(i,t,k,p)` identifies a log entry by index, term, kind, and protocol payload. Entries differing in kind or payload are distinct even when index and term match.

`LogicalLog(n)` is the current ordered logical log represented by `n`'s durable state, accepted unstable state, and installed snapshot prefix. Moving an entry between volatile and durable storage, or compacting a prefix into a snapshot that preserves it, is not logical deletion. Snapshot operations are in scope when they can affect the selected property.

`LogContains(n,i,e)` means the completed `LogicalLog(n)` contains entry `e` at index `i`.

`Leadership(n,t)` begins at `ElectionWon(n,t,C)` and ends when `n` leaves leader state or adopts a different term.

`LogAppend(n,e)` completes when `e` is appended at the then-current tail of `LogicalLog(n)`.

`LogReplaceOrDelete(n,i,old,new)` completes when an existing entry `old` at index `i` is removed or replaced by a distinct entry `new`. Physical movement without an identity change is not replacement or deletion.

## Commit and apply

`Committed(i,e,t)` completes at the first event that marks entry `e` at index `i` committed while acting in current term `t` and makes it eligible for state-machine delivery. This records what the implementation treats as committed without assuming its quorum, term, or durability logic is correct. Later propagation of the same commit does not create a different entry identity.

`Applied(n,i,e)` completes when `n`'s application boundary acknowledges applying entry `e` at index `i`. Merely returning an entry in an output batch is insufficient unless the public contract defines that as application completion.
