# mcp/atlas-evidence — FedClear ATO Evidence Logger

Python MCP server that exposes a single tool, `log_adjudication_evidence`,
which runs the full **ATLAS.Compliance.Logging** audit chain and produces a
tamper-evident, PII-redacted evidence package aligned with NIST 800-53.

---

## What this is

| File | Role |
|------|------|
| `atlas_logging.py` | **ATLAS-derived.** Faithful Python port of `C:\ATLAS\ATLAS.Compliance.Logging\Activities\*.xaml` — six workflows, stdlib only. |
| `server.py` | **FedClear glue.** FastMCP server that orchestrates the six ATLAS functions, adds hash-chain state persistence across calls, and exposes the result as a single MCP tool. |

---

## ATLAS / FedClear boundary

All code is annotated with one of two labels:

- `# [ATLAS]` — logic translated verbatim from a named XAML workflow in the source library.
  Do not modify these blocks without also updating `ATLAS.Compliance.Logging`.
- `# [FedClear]` — new work written for FedClear / AgentHack 2026.
  These blocks have no equivalent in the upstream library.

### Workflow-to-function map

| ATLAS workflow (`Activities/*.xaml`) | Python function (`atlas_logging.py`) |
|--------------------------------------|--------------------------------------|
| `Get_RunContext.xaml` | `get_run_context()` |
| `Redact_PII_Text.xaml` | `redact_pii_text()` |
| `Log_NIST_AuditEvent.xaml` | `log_nist_audit_event()` |
| `Hash_And_Chain_Audit.xaml` | `hash_and_chain_audit()` |
| `Apply_Retention_Policy.xaml` | `apply_retention_policy()` |
| `Build_AuditEvidencePacket.xaml` | `build_audit_evidence_packet()` |

### What FedClear adds (not in ATLAS)

- **Hash-chain state persistence** — `audit.jsonl.hashchain.state` survives across MCP
  tool calls so consecutive adjudications build a continuous chain on the same log.
- **`.hashchain` sidecar** — JSONL file binding each `audit_event_id` to its
  `record_hash` / `chained_hash` for independent verification.
- **MCP tool wrapper** — `log_adjudication_evidence` in `server.py` orchestrates
  the six ATLAS steps in order and returns all artifact paths in one response.
- **`event_type = "ato.adjudication"`** — FedClear-specific event type injected into
  the JSONL `event_type` field (ATLAS leaves this as a caller-supplied parameter).

---

## Tool: `log_adjudication_evidence`

### Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `finding_id` | str | required | ATO finding ID (e.g. `ATO-10011`) |
| `agent_decision` | str | required | `auto_clear` \| `escalate` \| `mandatory_review` |
| `reasoning` | str | required | Agent justification text |
| `nist_controls` | list | required | NIST 800-53 control IDs |
| `evidence_refs` | list | required | Evidence artifact references |
| `raw_text` | str | `null` | Optional free-text to PII-redact |
| `output_dir` | str | `./output/` | Directory for all artifacts |
| `retention_class` | str | `FISMA-HIGH` | Retention classification |
| `retention_years` | int | `6` | Retention period |
| `replace_token` | str | `%[REDACTED]` | PII replacement string |
| `packet_id` | str | auto | Override auto-generated packet ID |

### Outputs

```jsonc
{
  "status": "success",
  "audit_event_id": "uuid",
  "packet_id": "ATLAS-PKT-20260609-153201-A3F7B2C1",
  "chained_hash": "64-char lowercase hex",
  "record_hash": "64-char lowercase hex",
  "written_at": "2026-06-09T15:32:01.123456Z",
  "artifact_paths": {
    "audit_log":         "/path/audit.jsonl",
    "hashchain_sidecar": "/path/audit.jsonl.hashchain",
    "retention_sidecar": "/path/audit.jsonl.retention.json",
    "evidence_zip":      "/path/ATLAS-PKT-....zip"
  },
  "redaction_summary": { "count": 2, "detected_types": ["ssn", "email"] },
  "retention": { "class": "FISMA-HIGH", "years": 6, "expiry_date": "..." }
}
```

### Audit JSONL record schema

```jsonc
{
  "audit_event_id": "uuid",
  "written_at":     "ISO 8601 UTC",
  "event_type":     "ato.adjudication",
  "control_ids":    ["AC-2", "AU-12"],
  "run_context":    { "MachineName": "...", "UserName": "...", ... },
  "payload":        { "finding_id": "...", "agent_decision": "...", ... },
  "schema_version": "atlas.compliance.logging.v1"
}
```

---

## PII redaction order (ATLAS contract — do not change)

1. SSN — `\b\d{3}-\d{2}-\d{4}\b`
2. Account / card numbers — `\b(?:\d[ -]*?){13,19}\b`
3. US phone — `\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b`
4. Email — `\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b`

---

## Hash-chain algorithm (ATLAS contract)

```
record_hash  = SHA-256( UTF-8(record_json_line) )
chained_hash = SHA-256( UTF-8(prev_chained_hash + record_json_line) )
```

First call: `prev_chained_hash = ""` → `chained_hash == record_hash`.

---

## Installation

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python server.py
# or
mcp run server.py
```

## Register with AgentHub (command-type MCP server)

```bash
uip agenthub mcp create command \
  --name "Atlas Evidence Logger" \
  --slug atlas-evidence \
  --description "FedClear ATO adjudication evidence logger" \
  --command python --arg server.py \
  --folder-path Shared
```

---

## Runtime output files

All written to `output/` (gitignored):

| File | Description |
|------|-------------|
| `audit.jsonl` | Append-only JSONL audit log |
| `audit.jsonl.hashchain` | Hash-chain sidecar (append-only) |
| `audit.jsonl.hashchain.state` | Prev-hash state for chain continuity |
| `audit.jsonl.retention.json` | Retention sidecar (overwritten each call) |
| `ATLAS-PKT-{ts}-{guid8}.zip` | Evidence ZIP (new file per call) |

---

*FedClear — UiPath AgentHack 2026 Track 1 (Maestro Case) — Karthik Kapula / ATLAS Labs*
