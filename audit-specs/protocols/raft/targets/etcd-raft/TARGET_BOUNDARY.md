# etcd/raft Target Boundary

Audit the complete `etcd/raft` working tree at `TARGET_ROOT` as an independent implementation.

The target library implements the consensus state machine; network, disk I/O, host scheduling, and application behavior may be caller responsibilities. Public README files, package documentation, API comments, and existing tests are available as contract evidence. Distinguish a library defect from a chain that requires violation of a specific inspected caller obligation.

Use this experiment boundary:

```text
participant count = symbolic over supported fixed-membership configurations
membership = fixed
public interfaces = all supported paths relevant to a finding
storage-processing modes = synchronous and asynchronous modes
PreVote = false and true
snapshots = included
read-only modes = included
leadership transfer = included
client exactly-once semantics = excluded
resource exhaustion = excluded
```

Inclusion does not require exhaustive inspection of a mechanism that cannot affect the current conclusion. Determine relevance from executable call paths, and identify when a path is unrelated or shares already-inspected code. Do not infer correctness thresholds or protocol formulas from this boundary; derive them from the materials available to the current audit arm or from inspected source.
