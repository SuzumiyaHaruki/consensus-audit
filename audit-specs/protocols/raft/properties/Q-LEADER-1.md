# Q-LEADER-1 — Leader completeness

If `Committed(i,e,t)` occurs and `ElectionWon(c,u,C)` later occurs with `u > t`, then `LogContains(c,i,e)` must hold when `c` completes that election.
