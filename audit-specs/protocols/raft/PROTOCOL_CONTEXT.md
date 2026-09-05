# Raft Audit Context

Project-authored notation for discussing Raft requirements. This glossary is not extracted protocol source and is not automatically loaded into model tasks.

```text
C: the current fixed voter set
Majority(C): any subset of C with size floor(|C| / 2) + 1
```

Related project vocabulary appears in `EVENT_SEMANTICS.md`. These definitions do not supply additional protocol guarantees or map events to target source. Any adopted completion interpretation must be justified using registered protocol sources and the actual target's interface contracts.
