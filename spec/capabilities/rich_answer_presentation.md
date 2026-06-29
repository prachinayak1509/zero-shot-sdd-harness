# Capability: Rich Answer Presentation

> Phase 2. Builds on [adaptive_analysis_loop](adaptive_analysis_loop.md).

## What It Does
Enriches each answer with an agent-chosen interactive chart, an aggregated result table, 2–3 suggested follow-up questions, and surfaces data-quality flags (nulls, outliers, anomalies) on the profile.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question + result | from the analysis loop | graph state | yes |
| profile | JSON | stored Dataset | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | object (type + encodings) | API response → Charts tab (Recharts) |
| table | object (columns + rows) | API response → Result Table tab |
| follow_ups | string[] (2–3) | API response → follow-ups strip |
| quality_flags | object (null %, outlier flags, anomaly notes) | stored on Dataset profile → quality badges |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | choose chart type + propose follow-ups | degrade: omit chart/follow-ups, still return prose+table |
| pandas (profiling service) | compute null counts + IQR outliers | partial: flag what computed, continue |

## Business Rules
- Chart type is chosen by the agent based on the result shape (e.g. categorical→bar, time→line); when no chart fits, `chart_spec` is null and the Charts tab says so.
- The result table is the actual aggregated rows the code produced — not a re-query.
- Follow-up suggestions are clickable and re-ask in the same conversation.
- Quality flags are computed deterministically (no LLM) where possible.

## Success Criteria
- [ ] A grouping question returns a `chart_spec` with a valid `type` and a `table` with ≥2 rows from the 5000-row fixture.
- [ ] ≥2 clickable `follow_ups` are returned; clicking one asks it in the same conversation.
- [ ] The profile shows real data-quality badges (null %, outlier flag) computed from the file.
