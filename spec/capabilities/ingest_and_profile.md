# Capability: Ingest and Profile

## What It Does
Accepts an uploaded CSV, stores it locally, and auto-computes a profile (columns, dtypes, row count, per-column ranges and null counts) shown to the user.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV upload | `POST /api/datasets` multipart | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | Dataset row | SQLite (see [data.md](../data.md)) |
| raw file | file | local file store |
| profile | JSON (columns, dtypes, ranges, null counts, sample) | API response → profile panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local file store | write raw upload | fatal → `storage_error` |
| pandas | load + describe the file | invalid/unparseable → `invalid_file` (400) |
| SQLite | persist Dataset + profile | fatal → `storage_error` |

## Business Rules
- Original file is never mutated; it is stored as-is.
- No LLM call — profiling is pure pandas, so it is fast and free.
- Files too large to hold in memory are rejected (out of scope), not partially loaded.
- Profile carries only schema/stats and a bounded sample (≤20 rows) for later prompts — never the full data into any prompt.

## Success Criteria
- [ ] Uploading a valid CSV returns a profile whose `column count` equals the real file's column count and `row_count` equals the real row count.
- [ ] Per-column `dtype`, `min`/`max` (numeric), and `null_count` are computed from the real file.
- [ ] A non-CSV or unparseable upload returns a 400 `invalid_file` and creates no Dataset row.
- [ ] `GET /api/datasets/{id}` returns the same stored profile after a reload.
