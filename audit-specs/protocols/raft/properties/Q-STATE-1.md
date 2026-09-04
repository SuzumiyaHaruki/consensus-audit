# Q-STATE-1 — State-machine safety

If `Applied(a,i,x)` and `Applied(b,i,y)` occur, then `x = y`. Evaluate the execution history, not only final log snapshots. Reapplying the same command is outside this property's exactly-once scope.
