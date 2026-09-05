# Hidden M6 trigger test

`m6_maybe_append_test.go` verifies the local M6 mechanism: a follower with a conflicting tail entry must replace that entry when a leader sends an empty entry at the same index followed by a non-empty proposal. The correct target passes; `target-v6` fails because it skips the first entry during conflict detection.

The test is evaluator-only. Do not copy it into a target before an LLM audit, do not add it to `audit-specs`, and do not expose this directory through the source tools. `run_m6_maybe_append.sh` copies the target and test into a fresh `/tmp` directory, so the original target tree remains unchanged.

Run after an audit:

```bash
evaluation/hidden-tests/run_m6_maybe_append.sh --target-root /home/nitro/Desktop/etcd-raft clean
evaluation/hidden-tests/run_m6_maybe_append.sh --target-root /home/nitro/Desktop/experiments-etcd-raft/target-v6 mutant
```
