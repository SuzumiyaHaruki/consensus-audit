# Q-LOG-1 — Leader append-only

While `Leadership(n,t)` holds, no `LogReplaceOrDelete(n,i,old,new)` event may complete for an entry that had become part of `LogicalLog(n)` at any earlier point in that leadership interval. Tail `LogAppend` events are allowed.
