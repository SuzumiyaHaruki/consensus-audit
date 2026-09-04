# Raft Audit Context

Notation shared by the Raft property set:

```text
C: the current fixed voter set
Majority(C): any subset of C with size floor(|C| / 2) + 1
```

The selected property uses the abstract events and completion points defined in `EVENT_SEMANTICS.md`. These definitions are protocol-level requirements, not a map to target source code. The auditor must identify and justify the corresponding implementation completion points.
