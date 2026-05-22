# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

FedClear is a UiPath AgentHack 2026 (Track 1: Maestro Case) submission. It automates federal Authority to Operate (ATO) security-finding triage: an AI agent maps findings to NIST 800-53 controls, assembles evidence packages, and routes ambiguous or high-risk cases to a human reviewer. Solo submission by Karthik Kapula (ATLAS Labs).

**All data is synthetic/mock. Never commit real agency data, real findings, or real PII.**

Claude Code usage here counts toward the AgentHack bonus. Save verifiable evidence of each meaningful session to `docs/coding-agent/` and add a row to `CODING_AGENTS.md`.

## Repository Layout

```
/agents       Triage & decisioning agent(s) (UiPath Agent Builder / coded agent)
/maestro      Maestro Case definition — stages: Intake → Triage → Evidence → Review → Sign-off
/process      Supporting UiPath workflows
/mock-data    Synthetic ATO findings (findings.json) — five canonical test cases
/docs         Architecture, NIST 800-53 mapping, diagrams
/docs/coding-agent   Claude Code session exports / screenshots (evidence for bonus scoring)
/scripts      Repo setup helpers (init-repo.sh — run once, locally)
```

## Mock Data Schema

`mock-data/findings.json` is the seed dataset. Each finding has:
- `id`, `source_system`, `title`, `raw_description`, `severity_hint`
- `suggested_nist_control` + optional `alternate_controls` (ambiguous cases)
- `evidence_refs[]` — empty array = missing-evidence scenario
- `confidence_inputs.scanner_confidence` + `control_match_score`
- `finding_type`: one of `auto_clearable` | `low_confidence` | `high_severity` | `conflicting_mapping` | `missing_evidence`

The five seed findings cover one of each `finding_type` — use them as test cases when building and validating the triage agent decision logic.

## Core Decision Logic (Triage Agent)

The agent must implement these routing rules:
1. **Auto-clear** — high confidence + low/medium severity → agent resolves
2. **Escalate (low confidence)** — either confidence score below threshold → human review
3. **Mandatory sign-off** — `severity_hint == "Critical"` → always human review, regardless of confidence
4. **Ambiguous mapping** — multiple `alternate_controls` with no clear winner → human review
5. **Missing evidence** — empty `evidence_refs` → request evidence via reviewer

## External Dependency

`ATLAS.Compliance.Logging` is a pre-existing open-source library used for evidence/audit primitives. It is referenced as an external dependency. Code that wraps or calls it must be marked as such in-source to preserve the AgentHack new-work boundary.

## Commit Identity

All commits must be authored as Karthik Kapula. The AgentHack Section 8 winner verification checks the contribution record.
