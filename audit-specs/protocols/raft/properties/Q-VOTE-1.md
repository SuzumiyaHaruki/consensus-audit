# Q-VOTE-1 — One vote per term

For every node `n` and term `t`, `{c | VoteGranted(n,t,c)}` contains at most one distinct candidate, including across crash and restart. Repeated completed grants for the same candidate do not violate this property.
