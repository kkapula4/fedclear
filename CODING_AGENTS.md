# Coding-Agent Evidence (AgentHack Bonus)

This file backs the **+2 Platform Usage bonus** in AgentHack judging (Phase 1 & 2).

> **Hard rule: evidence must reflect real Claude Code usage. Never fabricate prompt
> logs, sessions, or screenshots.** Fabricated evidence fails Section 8 winner
> verification and undermines the entire submission. Accurate documentation of real
> usage is what scores — and it is the only version that holds up.

## Bonus scoring (from official rules)

| Tier | Requirement |
|------|-------------|
| 2 pts | Tool documented + how it contributed + meaningfully integrated, with at least one verifiable evidence artifact (prompt/session export, screenshots, or dedicated README section) |
| 1 pt | Documented but partial or only partially verifiable |
| 0 pts | Not documented or unverifiable |

## Required documentation (must also appear in README + Devpost description)

- **(a) Tool:** Claude Code, via UiPath for Coding Agents
- **(b) Contribution:** _describe concretely — e.g., scaffolded the triage agent,
  generated Maestro stage-transition workflows, wrote ATLAS integration code_
- **(c) Verifiable evidence:** committed under `docs/coding-agent/`

## Evidence index

| Date | What Claude Code did | Evidence file (in `docs/coding-agent/`) |
|------|----------------------|------------------------------------------|
| 2026-05-22 | Built `agents/triage_agent.py` from scratch — pure stdlib Python, implements the 5 routing rules from CLAUDE.md, processes `mock-data/findings.json`, outputs `agents/triage_report.json`. Fixed ambiguous-mapping notes parser mid-session. Final run: 100% accuracy on all 30 synthetic findings. | [2026-05-22-triage-agent-session.md](docs/coding-agent/2026-05-22-triage-agent-session.md) |
| 2026-05-26 | Built FedClear Triage Agent in UiPath Agent Builder (gpt-5.4, Precise, max_iterations=1) — system prompt encodes 5 routing rules from triage_agent.py. Published as v1.0.0. Verified 5/5 decision paths against Python reference (100% agreement, all reasoning lines cite correct rule). Built Agentic Process BPMN with service task wired to Maestro Case Triage stage. End-to-end debug run: 7 s, agent_decision=auto_clear, Error=null. 7 screenshots captured. | [2026-05-26-uipath-agent-build.md](docs/coding-agent/2026-05-26-uipath-agent-build.md) |
| 2026-06-09 | Read all 6 ATLAS.Compliance.Logging .xaml InvokeCode workflows; produced a faithful Python port (atlas_logging.py, [ATLAS]-annotated) + FastMCP server wrapper (server.py, [FedClear]-annotated) exposing a single tool log_adjudication_evidence. Two-call self-test independently proved SHA-256 hash-chain linkage across call boundaries. Registered as remote MCP server in AgentHub (Id 76a30820, --use-relay). | [2026-06-09-atlas-mcp-tool-session.md](docs/coding-agent/2026-06-09-atlas-mcp-tool-session.md) |

## Capture convention (do this as you build, not at the end)

1. After a meaningful Claude Code session, export or screenshot it.
2. Save it to `docs/coding-agent/` with a dated, descriptive filename.
3. Add a row to the evidence index above and to the Confluence
   "FedClear — Coding-Agent Evidence" page.
4. Keep a one-line note of *what it actually did* — not an exaggeration.
