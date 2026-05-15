# Phase 2 summary — Documentation parsed into entities

**Outputs**

- `build/graph/doc_entities.json` — 30 sections, 17 business rules, 4 open issues
- SOLUTION.md §1.5 (ambiguity register) seeded with 5 entries
- `build/reports/ambiguity_log.md` populated with full High-severity write-up

**Open issues recovered**

| ID                            | Source section                                 | Tickers   |
| ----------------------------- | ---------------------------------------------- | --------- |
| `functional_spec-§6.1`        | DM duplicates (resolved by dedup logic)        | —         |
| `SP-184`                      | Vendor B severity codes (deferred)             | SP-184    |
| `SP-227`                      | "First dose" vs "randomization" date for TRTEMFL | SP-227  |
| `functional_spec-§6.4`        | Site lookup join (char vs num type mismatch)   | —         |

**Static-analysis discovery confirmed by data scan**

The input file `input_data/ae.csv` contains 10 distinct `AESEV` values
including `GRADE 1` and `GRADE 2`, confirming the SP-184 issue is
load-bearing — `ground_truth/ae_summary.csv` contains blank-severity rows
that Phase 5 must reproduce.
