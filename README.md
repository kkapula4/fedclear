# FedClear — Agentic ATO Compliance Adjudication

UiPath Global AgentHack 2026 submission — **Track 1: UiPath Maestro Case**.
Solo entrant: Karthik Kapula (UiPath MVP, Solution Architect). Devpost entrant name: ATLAS Labs.

---

## Project Description

Federal Authority to Operate (ATO) reviews are slow, manual, and exception-heavy.
Security findings must be triaged, mapped to NIST 800-53 controls, evidenced, and
adjudicated — today largely by hand.

**FedClear** is an agentic case-management solution built on UiPath Maestro Case.
An AI agent triages incoming ATO security findings, maps each to the relevant
NIST 800-53 control(s), assembles tamper-evident evidence packages, and routes
ambiguous or high-risk findings to a human reviewer for sign-off. A human stays
in control at the ATO decision point.

> **Data scope:** All data is synthetic / mock. No real agency data is used anywhere.

## New-Work / Dependency Boundary (please read)

Per AgentHack rules, this submission is **newly created during the submission period**
(work started 2026-05-19). FedClear **builds on top of** the separately, previously
published open-source library `ATLAS.Compliance.Logging`, which is referenced here as
an **external dependency — not repackaged**. The new, original work in this repository
is the agentic adjudication layer: the Maestro Case design, the triage/decisioning
agent(s), the human-in-the-loop orchestration, and the integration code. Files and
modules that wrap or call the ATLAS dependency are marked as such in-source.

## UiPath Components

- UiPath Maestro (Case) — orchestration / governance layer
- UiPath Studio Web
- UiPath Orchestrator
- UiPath Agent Builder / coded agent (triage & decisioning)
- UiPath for Coding Agents (Claude Code) — used during the build (see below)
- External dependency: `ATLAS.Compliance.Logging` (evidence/audit primitives)

## Agent Type

<!-- Confirm and finalize before submission -->
This solution utilizes: **[Coded Agents / Low-code Agents / Both]** — _state explicitly here._

## Setup Instructions

<!-- Fill with exact, reproducible steps so judges can run it -->
1. Prerequisites: UiPath Automation Cloud access, Maestro enabled, ...
2. Import the Maestro Case definition from `/maestro`
3. Configure the agent(s) in `/agents`
4. Load mock data from `/mock-data`
5. Run end-to-end: ...

## Coding Agent Usage (AgentHack bonus)

This solution was built with the assistance of **Claude Code** via **UiPath for Coding Agents**.

- **Tool:** Claude Code (UiPath for Coding Agents)
- **Contribution:** _[fill: agent scaffolding, Maestro workflow generation, integration code, ...]_
- **Verifiable evidence:** see [`/docs/coding-agent/`](docs/coding-agent/) — prompt/session
  exports and screenshots. Evidence reflects actual usage only.

See [CODING_AGENTS.md](CODING_AGENTS.md) for the full evidence index.

## License

Apache License 2.0 — see [LICENSE](LICENSE). The open-source license applies solely to
the original solution code in this repository and does not extend to UiPath proprietary
tools, activities, SDK packages, or platform components, which remain under their own terms.

## Repository Layout

```
/agents       triage & decisioning agent(s)
/maestro      Maestro Case definition & stages
/process      supporting workflows
/mock-data    synthetic ATO findings (no real data)
/docs         architecture, NIST mapping, diagrams
/docs/coding-agent   coding-agent evidence (prompt logs, screenshots)
/scripts      repo / setup helpers
```
