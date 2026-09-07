# Studies

One-off research code, kept apart from the application.

Nothing here is imported by `catalog/`, `ingest/` or `sources/`, nothing
here runs at request time, and nothing here is covered by the test
suite. These are the scripts that produced a written finding in the
documentation, kept so that the finding can be checked and extended.

**The scripts are as they ran.** They are not reformatted, tidied or
refactored, and `studies/` is excluded from the linter for that reason.
A cleaned-up script is a different script: if the cleanup changed
behaviour, the published numbers would no longer correspond to the
committed code, and that correspondence is the only reason to keep them.
Expect long lines, terse names and one-off argument handling.

Each study directory carries a README giving the order the scripts ran
in, what each produced, and what the scripts expect to find on disk.

| Study | Finding |
|---|---|
| `cataloging-practice/` | [Cataloging practice: a study](../docs/practice-study/index.md) |
