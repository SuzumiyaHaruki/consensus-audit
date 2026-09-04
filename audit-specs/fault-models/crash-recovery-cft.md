# Crash-Recovery CFT Fault Model

- A node may crash and later restart with the same identity.
- A crash loses all volatile state and performs no graceful flushing.
- Restart sees only writes that completed durable persistence before the crash.
- The network may delay, drop, duplicate, reorder, and later resume messages.
- The network does not forge messages or modify their protocol content.
- Nodes are not Byzantine. Incorrect protocol behavior caused by a software defect remains in scope.
- Completed durable writes are not corrupted. Torn writes, bit rot, and malicious storage are out of scope.
- Safety must hold even without a live quorum or eventual message delivery.

This fault model does not define the cluster size, quorum rule, membership scheme, or number of failures under which progress is required. Those belong to the selected protocol and experiment configuration. Any liveness claim must separately state its availability and eventual-delivery assumptions.
