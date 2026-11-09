# Manual review of judge decisions (ground-truth rule R10)

Judge: `gemini-3.5-flash`. Evaluated runs: `gemini-3.6-flash`. Reviewer: manual check of every item-level
decision against the matching rules in `data/ground_truth/re21_ground_truth.json`.

## 2026-11-09: RE21, incomplete description

| Run | Items | Agree | Disagree | Borderline |
|---|---:|---:|---:|---:|
| direct (`…113921Z_direct_incomplete_de484f`) | 8 | 8 | 0 | 2 |
| rag, full corpus (`…114003Z_rag_incomplete_811efe`) | 8 | 8 | 0 | 0 |
| rag_verify, full corpus (`…114305Z_rag_verify_incomplete_776b71`) | 8 | 8 | 0 | 0 |
| rag, documentation only (`…114851Z_rag_incomplete_9bdf79`) | 7 | 7 | 0 | 1 |
| rag_verify, documentation only (`…114935Z_rag_verify_incomplete_5b493a`) | 7 | 7 | 0 | 1 |
| direct, 2nd run from UI (`…114823Z_direct_incomplete_acead1`) | – | – | – | – |

The 2nd direct run is not judged yet: the free-tier quota for the judge model (20 requests/day/model) was exhausted on 2026-11-09.

All objective mappings were correct (o1 → f1 volume, o2 → f2 displacement).

### Borderline decisions (kept as judged, no overrides)

1. **"Truss geometry and node positions"** (direct, f2) was judged *vague*, so it is a false positive and L counts as missing for f2.
   Its relationship text mentions "orientation and length of bars", but the item names a category (geometry, node positions) rather than the bar length L. Rule R4 applies.
   If it were credited to L instead, f2 recall would rise from 6/8 to 7/8 and precision from 6/8 to 7/8.
2. **"Structural analysis model"** (direct, f2) and **"Truss structural analysis model"** (rag documentation-only, f2) were judged *not in implementation*.
   The displacement expression in DESDEO is the closed-form result of a truss analysis, so this is physically reasonable. But the implementation contains no model component, so rule R8 makes it a false positive.
   The item does not describe the formula itself, so it was not matched to `expr_displacement` (R6).

These two cases show where the reference definition, not the extractor, determines the score. They are
worth discussing with the advisor: should "a structural analysis is needed" count as identifying the
displacement expression?
