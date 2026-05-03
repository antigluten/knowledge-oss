# Log

Append-only timeline of vault operations. One line per ingest, synthesis, or
lint pass.

Format:

```
## [YYYY-MM-DD] <event> | <title>

<1-3 line context>
```

Events: `ingest`, `synthesis`, `query`, `lint`, `meta`.
