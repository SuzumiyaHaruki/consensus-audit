# Common candidate criteria

A Candidate is a source-supported hypothesis worth testing, not a confirmed bug or proof of reachability. Apply these criteria to every candidate:

- Connect an accepted requirement and its original source to an implementation obligation, a decisive mechanism and a minimal protocol contradiction. A preferred ordering or style is not itself a protocol guarantee.
- Support executable behavior with source personally returned by read_file in this task. Search hits, symbol names, comments, papers and API documentation suggest relationships or express guarantees and intent; none proves that the executable implementation enforces a guarantee.
- Missing evidence is not evidence of missing protection. Follow relevant guards, helpers and completion paths before treating an apparent absence as an implementation mechanism. Preserve missing dependencies as unknowns.
- Do not insert the violation being explained directly into the precondition. Explain which implementation actions and permitted faults could produce the problematic state, and how that state leads to a contradiction grounded in the supplied protocol sources.
- Provide a minimal causal chain and P/A/V/O: concrete preconditions, actions, the resulting violation and an observable test oracle. State the roles of unavailable host, transport, storage and application code, including inspected caller obligations. Verify decisive arithmetic against boundary cases.
- Reachability and integration conditions may remain unconfirmed; state those limitations explicitly. Do not discard a supported mechanism solely because execution is unavailable, but do not claim a protocol violation if the connection to the actual requirement is unsupported.
- Without execution evidence, never claim a confirmed defect. Available tools only list, search and read source or registered materials; they cannot execute tests, modify files or invoke arbitrary commands. Do not use Git history, mutations, evaluation results, remembered upstream implementations or project reputation to infer defects.

Keep independent mechanisms separate. Combine requirement links for the same mechanism within this task. One candidate does not establish that any other requirement has been checked, and no_candidate does not prove correctness.
