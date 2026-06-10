# Claude Code Session — ATLAS Evidence Logger MCP Tool (2026-06-09)

**Project:** FedClear — AgentHack 2026, Track 1 (Maestro Case)  
**Date:** 2026-06-09  
**Tool:** Claude Code (uipath-mcp-servers + uipath-rpa skills)  
**Reference:** SCRUM-28

---

## What was built

1. **`mcp/atlas-evidence/atlas_logging.py`** — faithful Python port of all six `ATLAS.Compliance.Logging` InvokeCode workflows (`C:\ATLAS\ATLAS.Compliance.Logging\Activities\*.xaml`). Pure stdlib. Each function maps 1-to-1 to its XAML source and is annotated `# [ATLAS]` on every translated block.

2. **`mcp/atlas-evidence/server.py`** — FedClear MCP wrapper (`[FedClear]` annotated throughout). FastMCP server exposing a single tool `log_adjudication_evidence` that orchestrates the six ATLAS steps in canonical order and adds hash-chain state persistence across calls.

3. **AgentHub registration** — server registered as a remote MCP server in AgentHub (Id `76a30820`, remote-type with relay, `Shared` folder, slug `atlas-evidence`).

---

## Session steps

### Step 1 — Read the six ATLAS source workflows

Used the **uipath-rpa** skill to open and read each `.xaml` file in
`C:\ATLAS\ATLAS.Compliance.Logging\Activities\`:

| XAML workflow | Core logic (InvokeCode) |
|---------------|------------------------|
| `Get_RunContext.xaml` | Reads `Environment.MachineName`, `Environment.UserName`, and four UiPath env vars; emits a context dict with `DateTime.UtcNow` in `"o"` format |
| `Redact_PII_Text.xaml` | Applies four regex patterns (SSN → account → phone → email) in fixed order; count of matches per type |
| `Log_NIST_AuditEvent.xaml` | Builds a 7-field JSONL record (steps `[6a]`–`[6g]`); appends with `File.AppendAllText`; `Formatting.None + NewLine` |
| `Hash_And_Chain_Audit.xaml` | `record_hash = SHA-256(record)`; `chained_hash = SHA-256(prevHash + record)`; UTF-8 encoding; 64-char lowercase hex |
| `Apply_Retention_Policy.xaml` | Writes `{path}.retention.json` sidecar; `DateTime.AddYears(N)` with Feb-29 clamp; NIST controls AU-11, SI-12 |
| `Build_AuditEvidencePacket.xaml` | Streams SHA-256 of audit log via `ComputeHash(FileStream)`; writes manifest + log into a ZIP at `CompressionLevel.Optimal`; refuses to overwrite existing ZIP |

### Step 2 — Python port: `atlas_logging.py`

Translated each InvokeCode block to an equivalent Python function in `atlas_logging.py`. Key fidelity decisions:

- `_utc_iso_o()` replicates C# `DateTime.UtcNow.ToString("o")` exactly (microsecond precision + `Z` suffix, not `+00:00`).
- `_sha256_hex()` matches `BitConverter.ToString(sha256.ComputeHash(bytes)).Replace("-","").ToLowerInvariant()`.
- `_sha256_file()` reads in 64 KB chunks to match `ComputeHash(FileStream)` streaming behaviour.
- `_add_years()` reproduces the Feb-29 clamp in `DateTime.AddYears`.
- PII regex patterns copied verbatim; application order is a contract (SSN before account prevents partial-digit false positives on card numbers).
- `Build_AuditEvidencePacket` error text for existing-ZIP case matches the XAML exactly: _"federal forensics requires atomic packet creation"_.

Every line derived from a XAML InvokeCode block is tagged `# [ATLAS]`. The one extension that has no ATLAS equivalent — returning `json_line` from `log_nist_audit_event()` so the caller can feed it directly into `hash_and_chain_audit()` — is tagged `# [FedClear]`.

### Step 3 — MCP wrapper: `server.py`

Written as entirely new FedClear work (no equivalent in ATLAS). The file is annotated `# [FedClear]` throughout.

`log_adjudication_evidence` orchestrates the six steps in order:

```
1. get_run_context()             — [ATLAS]
2. redact_pii_text()             — [ATLAS]
3. log_nist_audit_event()        — [ATLAS]
4. hash_and_chain_audit()        — [ATLAS]
5. apply_retention_policy()      — [ATLAS]
6. build_audit_evidence_packet() — [ATLAS]
```

FedClear additions in `server.py` (not in ATLAS):

- **Hash-chain state persistence** — `audit.jsonl.hashchain.state` stores `prev_chained_hash` across MCP tool calls so consecutive adjudications form a continuous chain.
- **`.hashchain` sidecar** — append-only JSONL that binds each `audit_event_id` to its `record_hash` / `chained_hash` for independent verification.
- **`event_type = "ato.adjudication"`** — FedClear-specific JSONL field value.
- Entry-point transport flag: `--transport streamable-http` (default: `stdio`), added in a follow-up commit.

Tool inputs (11 parameters): `finding_id`, `agent_decision`, `reasoning`, `nist_controls`, `evidence_refs`, `raw_text`, `output_dir`, `retention_class` (default `FISMA-HIGH`), `retention_years` (default `6`), `replace_token`, `packet_id`.

Tool output includes: `status`, `audit_event_id`, `packet_id`, `chained_hash`, `record_hash`, `written_at`, `artifact_paths` (4 files), `redaction_summary`, `retention`.

### Step 4 — Two-call self-test (hash-chain verification)

Ran the server locally and called `log_adjudication_evidence` twice against two synthetic ATO findings.

The test independently verified the SHA-256 hash-chain invariant by recomputing outside the server:

```
call 1: prev_hash = ""
  → chained_hash_1 == record_hash_1   (first-record invariant)

call 2: prev_hash = chained_hash_1
  → SHA-256( UTF-8(chained_hash_1 + call2_json_line) ) == chained_hash_2   ✓
```

Both equalities held, confirming that the Python port replicates the ATLAS `Hash_And_Chain_Audit.xaml` algorithm correctly across call boundaries.

### Step 5 — AgentHub registration

Registered the server as a remote MCP server in AgentHub using the **uipath-mcp-servers** skill:

```
uip agenthub mcp create remote \
  --name "atlas-evidence" \
  --slug atlas-evidence \
  --uri http://127.0.0.1:8000/mcp \
  --use-relay \
  --folder-path Shared
```

AgentHub assigned Id `76a30820`. The server is validly registered in the Shared folder as `atlas-evidence`. However, a live cloud→local relay call is blocked in this environment: the relay requires a Shared-scoped machine, and the only available machine is PersonalWorkspace-scoped. For the demo, the tool is invoked deterministically and the architecture is described.

---

## ATLAS / FedClear boundary summary

| Marker | Meaning | Files |
|--------|---------|-------|
| `# [ATLAS]` | Logic translated verbatim from a named `.xaml` InvokeCode block | `atlas_logging.py` |
| `# [FedClear]` | New work written for FedClear / AgentHack 2026; no equivalent in ATLAS | `server.py`, plus the `json_line` return extension in `atlas_logging.py` |

The runtime has no dependency on the ATLAS UiPath project — all algorithms are re-implemented in Python stdlib.

---

## Commits

`602e276` — `Add ATLAS Evidence Logger MCP tool (Phase 1): faithful Python port of ATLAS.Compliance.Logging, agent-callable single tool log_adjudication_evidence, with ATLAS-vs-FedClear dependency-boundary markers and runtime-verified hash chaining`  
`d543713` — `Enable streamable-http transport on ATLAS evidence MCP server (--transport flag, stdio default preserved); registered as remote MCP server in AgentHub`  
Branch: `main` — pushed to `origin`.
