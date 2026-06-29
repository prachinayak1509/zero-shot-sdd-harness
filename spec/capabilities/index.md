# Capabilities Index

> **Boilerplate status:** The spec-writer sub-agent creates one file per capability in this directory. Each file describes exactly one discrete thing the agent can do.

---

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs. Examples:
- "Search the web for companies matching criteria X"
- "Draft a personalized email given a lead profile"
- "Send a Slack notification when a threshold is crossed"

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| Ingest & profile a spreadsheet | [ingest_and_profile.md](ingest_and_profile.md) | 1 |
| Adaptive analysis loop (coded answer in a sandbox) | [adaptive_analysis_loop.md](adaptive_analysis_loop.md) | 1 |
| Rich answer presentation (charts, tables, follow-ups, quality flags) | [rich_answer_presentation.md](rich_answer_presentation.md) | 2 |
| Persistent workspace (sessions, multi-file, recipes, cost, trace) | [persistent_workspace.md](persistent_workspace.md) | 3 |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file should answer:
- **What it does** (one sentence)
- **Inputs** (what data it receives)
- **Outputs** (what it produces)
- **External calls** (APIs, LLMs, databases it touches)
- **Error cases** (what can go wrong and how it's handled)
- **Success criteria** (how we test it)
