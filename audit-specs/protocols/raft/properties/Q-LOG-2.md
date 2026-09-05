# Q-LOG-2 — Log matching

For any completed states of nodes `a` and `b`, if `LogicalLog(a)` and `LogicalLog(b)` contain entries with the same entry term at the same index `i`, then their logical prefixes through `i` contain identical `Entry(index,term,kind,payload)` values in the same order.

## Equivalent violation form

A violation exists when there are nodes `a`, `b` and indices `j <= i` such that both logical logs contain an entry at index `i` with the same term, but their entries at `j` differ in term, kind, or payload. The differing position `j` may be earlier than `i`; a payload difference at `i` is not required.
