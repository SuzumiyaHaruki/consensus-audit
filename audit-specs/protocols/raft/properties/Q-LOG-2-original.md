# Q-LOG-2 — Log matching

For any completed states of nodes `a` and `b`, if `LogicalLog(a)` and `LogicalLog(b)` contain entries with the same entry term at the same index `i`, then their logical prefixes through `i` contain identical `Entry(index,term,kind,payload)` values in the same order.
