# Q-TERM-1 — Term monotonicity

For every node `n`, completed `DurableTerm(n,t)` events are non-decreasing in execution order. After `DurableTerm(n,t)`, neither later execution nor crash recovery may produce `ActsInTerm(n,u,a)` with `u < t`.

Losing a higher term that existed only in volatile state and was never durably completed is not a violation.
