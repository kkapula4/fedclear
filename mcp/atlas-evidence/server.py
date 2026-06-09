"""
server.py — FedClear MCP server: log_adjudication_evidence

[FedClear] This file is new work written for FedClear / AgentHack 2026.
It orchestrates the ATLAS.Compliance.Logging chain (atlas_logging.py) in the
exact six-step order, adds hash-chain state persistence, and exposes everything
as a single MCP tool.

ATLAS-derived logic lives entirely in atlas_logging.py (marked [ATLAS] there).
Every block here that is pure FedClear glue is marked [FedClear].

AgentHub registration (run once after deploying):
    uip agenthub mcp create command \
        --name "Atlas Evidence Logger" \
        --slug atlas-evidence \
        --description "FedClear ATO adjudication evidence logger" \
        --command python --arg server.py \
        --folder-path Shared
"""

import json
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

import atlas_logging as atlas   # [ATLAS] port of C:\ATLAS\ATLAS.Compliance.Logging

# ─────────────────────────────────────────────────────────────────────────────
# [FedClear] Server bootstrap
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="atlas-evidence",
    instructions=(
        "FedClear ATO adjudication evidence logger. "
        "Ports ATLAS.Compliance.Logging (C:\\ATLAS\\ATLAS.Compliance.Logging) for MCP tool use. "
        "Produces tamper-evident, PII-redacted JSONL audit records, hash chains, "
        "retention sidecars, and ZIP evidence packets aligned with NIST 800-53."
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# [FedClear] Hash-chain state helpers
# State file persists prev_chained_hash across MCP tool invocations so that
# consecutive calls build a continuous chain on the same audit log.
# ─────────────────────────────────────────────────────────────────────────────

_STATE_FILENAME = "audit.jsonl.hashchain.state"
_HASHCHAIN_SUFFIX = ".hashchain"


def _load_prev_hash(output_dir: str) -> str:
    """[FedClear] Read the last chained_hash from the state file.
    Returns '' for the very first call (first-record invariant: chained == record).
    """
    state_path = os.path.join(output_dir, _STATE_FILENAME)
    if os.path.isfile(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f).get("prev_chained_hash", "")
        except (json.JSONDecodeError, OSError):
            return ""
    return ""


def _save_prev_hash(output_dir: str, chained_hash: str) -> None:
    """[FedClear] Persist the latest chained_hash for the next invocation."""
    state_path = os.path.join(output_dir, _STATE_FILENAME)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"prev_chained_hash": chained_hash}, f)


def _append_hashchain_sidecar(
    hashchain_path: str,
    audit_event_id: str,
    record_hash: str,
    chained_hash: str,
) -> None:
    """[FedClear] Append one JSONL entry to the .hashchain sidecar.
    Each line binds an audit_event_id to its record_hash and chained_hash so
    that the chain can be independently verified by replaying the ATLAS algorithm.
    """
    entry = json.dumps(
        {
            "audit_event_id": audit_event_id,
            "record_hash":    record_hash,
            "chained_hash":   chained_hash,
            "timestamp":      atlas._utc_iso_o(),   # call-time UTC stamp
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    with open(hashchain_path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# [FedClear] Default output directory
# Resolved relative to this file so the server works from any working directory.
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


# ─────────────────────────────────────────────────────────────────────────────
# MCP tool: log_adjudication_evidence
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def log_adjudication_evidence(
    finding_id: str,
    agent_decision: str,
    reasoning: str,
    nist_controls: list,
    evidence_refs: list,
    raw_text: Optional[str] = None,
    output_dir: Optional[str] = None,
    retention_class: str = "FISMA-HIGH",
    retention_years: int = 6,
    replace_token: str = "%[REDACTED]",
    packet_id: Optional[str] = None,
) -> dict:
    """Log an adjudicated ATO finding as a tamper-evident, PII-redacted audit evidence packet.

    Runs the full ATLAS.Compliance.Logging chain in the canonical order:
      1. Build run context   (Get_RunContext.xaml port)
      2. Redact PII          (Redact_PII_Text.xaml port — SSN → account → phone → email)
      3. Write JSONL record  (Log_NIST_AuditEvent.xaml port — schema atlas.compliance.logging.v1)
      4. Hash-chain it       (Hash_And_Chain_Audit.xaml port — SHA-256, 64-char hex, UTF-8)
      5. Apply retention     (Apply_Retention_Policy.xaml port — schema atlas.compliance.retention.v1)
      6. Build evidence ZIP  (Build_AuditEvidencePacket.xaml port — schema atlas.compliance.evidence.v1)

    Args:
        finding_id      : Unique identifier of the ATO finding (e.g. "ATO-10011").
        agent_decision  : Triage outcome: "auto_clear" | "escalate" | "mandatory_review".
        reasoning       : Agent's free-text justification.
        nist_controls   : List of NIST 800-53 control IDs mapped to the finding.
        evidence_refs   : List of evidence artifact references (paths, URLs, etc.).
        raw_text        : Optional free-text to PII-redact before including in the record.
        output_dir      : Directory for all output artifacts (default: ./output/).
        retention_class : Retention classification label (default: "FISMA-HIGH").
        retention_years : Retention period in years (default: 6).
        replace_token   : PII replacement string (default: "%[REDACTED]").
        packet_id       : Optional explicit packet ID; auto-generated if omitted.

    Returns a dict with artifact paths, packet_id, chained_hash, and redaction summary.
    """

    # ── [FedClear] Resolve output directory ──────────────────────────────────
    out_dir: str = output_dir or _DEFAULT_OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    audit_log_path: str  = os.path.join(out_dir, "audit.jsonl")
    hashchain_path: str  = audit_log_path + _HASHCHAIN_SUFFIX

    # ── STEP 1: Get_RunContext  [ATLAS] ───────────────────────────────────────
    run_context: dict = atlas.get_run_context()

    # ── STEP 2: Redact_PII_Text  [ATLAS] ─────────────────────────────────────
    # redact_pii_text operates on raw_text only; the JSONL payload's structured
    # fields (finding_id, agent_decision, reasoning) are assembled after redaction.
    redaction_result: dict = {"redaction_count": 0, "detected_types": [], "redacted_text": ""}
    redacted_raw: Optional[str] = raw_text

    if raw_text:
        redaction_result = atlas.redact_pii_text(
            input_text=raw_text,
            replacement=replace_token,
        )
        redacted_raw = redaction_result["redacted_text"]

    # [FedClear] Assemble the payload dict — always stores the post-redaction text.
    payload: dict = {
        "finding_id":     finding_id,
        "agent_decision": agent_decision,
        "reasoning":      reasoning,
        "evidence_refs":  list(evidence_refs or []),
    }
    if raw_text is not None:
        payload["raw_text"] = redacted_raw      # redacted form, never the original

    # ── STEP 3: Log_NIST_AuditEvent  [ATLAS] ─────────────────────────────────
    # redact_pii=False because we already applied Redact_PII_Text above (step 2).
    log_result: dict = atlas.log_nist_audit_event(
        event_type="ato.adjudication",          # [FedClear] FedClear-specific event type
        control_ids=nist_controls or [],
        payload=payload,
        run_context=run_context,
        output_path=audit_log_path,
        redact_pii=False,
    )

    # ── STEP 4: Hash_And_Chain_Audit  [ATLAS] ────────────────────────────────
    prev_hash: str = _load_prev_hash(out_dir)   # [FedClear] chain state across calls
    record_hash, chained_hash = atlas.hash_and_chain_audit(
        current_record=log_result["json_line"],  # serialised JSONL line (no trailing \n)
        prev_hash=prev_hash,
    )
    _save_prev_hash(out_dir, chained_hash)       # [FedClear] persist for next invocation
    _append_hashchain_sidecar(
        hashchain_path=hashchain_path,
        audit_event_id=log_result["audit_event_id"],
        record_hash=record_hash,
        chained_hash=chained_hash,
    )

    # ── STEP 5: Apply_Retention_Policy  [ATLAS] ──────────────────────────────
    retention_result: dict = atlas.apply_retention_policy(
        target_file_path=audit_log_path,
        retention_class=retention_class,
        retention_years=retention_years,
    )

    # ── STEP 6: Build_AuditEvidencePacket  [ATLAS] ───────────────────────────
    # Generate the packet ID here so we can use it for the ZIP filename as well.
    # If the caller supplied an explicit packet_id we pass it through; the ATLAS
    # function will use it verbatim.
    from datetime import datetime, timezone

    resolved_packet_id: str = (
        packet_id.strip()
        if packet_id and packet_id.strip()
        else (
            "ATLAS-PKT-"
            + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + "-"
            + __import__("uuid").uuid4().hex[:8].upper()
        )
    )
    zip_path: str = os.path.join(out_dir, resolved_packet_id + ".zip")

    packet_result: dict = atlas.build_audit_evidence_packet(
        audit_log_path=audit_log_path,
        output_zip_path=zip_path,
        packet_id=resolved_packet_id,
    )

    # ── [FedClear] Compose and return tool result ─────────────────────────────
    return {
        "status":          "success",
        "audit_event_id":  log_result["audit_event_id"],
        "packet_id":       packet_result["packet_id"],
        "chained_hash":    chained_hash,
        "record_hash":     record_hash,
        "written_at":      log_result["written_at"],
        "artifact_paths": {
            "audit_log":         audit_log_path,
            "hashchain_sidecar": hashchain_path,
            "retention_sidecar": retention_result["sidecar_path"],
            "evidence_zip":      packet_result["zip_path"],
        },
        "redaction_summary": {
            "count":          redaction_result["redaction_count"],
            "detected_types": redaction_result["detected_types"],
        },
        "retention": {
            "class":       retention_class,
            "years":       retention_years,
            "expiry_date": retention_result["expiry_date"],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
