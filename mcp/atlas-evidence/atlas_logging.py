"""
atlas_logging.py — faithful Python port of ATLAS.Compliance.Logging

Source library : C:\\ATLAS\\ATLAS.Compliance.Logging  (Activities\\*.xaml)
Schema version : atlas.compliance.logging.v1
Port author    : Karthik Kapula  (FedClear / AgentHack 2026)

Each public function maps 1-to-1 to a named XAML workflow in the source library.
Logic that is a direct translation of the ATLAS InvokeCode block is marked [ATLAS].
Any addition made by FedClear (e.g. exposing json_line for chaining) is marked [FedClear].
This file has NO dependency on the ATLAS UiPath project at runtime — the algorithms
are re-implemented here in Python stdlib so that the MCP server runs without UiPath.
"""

import hashlib
import re
import json
import zipfile
import os
import uuid
import platform
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers  (not exposed as workflow equivalents)
# ─────────────────────────────────────────────────────────────────────────────

def _utc_iso_o() -> str:
    """[ATLAS] ISO 8601 'o'-format UTC timestamp.
    Equivalent to C# DateTime.UtcNow.ToString("o") — uses microseconds + Z suffix.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _add_years(dt: datetime, years: int) -> datetime:
    """[ATLAS] Port of C# DateTime.AddYears(N).
    Handles the Feb-29 edge case by clamping to Feb-28 on non-leap target years.
    """
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        return dt.replace(year=dt.year + years, day=28)


def _sha256_hex(data: bytes) -> str:
    """[ATLAS] SHA-256 → 64-char lowercase hex.
    Equivalent to BitConverter.ToString(sha256.ComputeHash(bytes))
                              .Replace("-", "").ToLowerInvariant()
    """
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str) -> str:
    """[ATLAS] Streaming SHA-256 of a file — port of the ComputeHash(FileStream) call
    in Build_AuditEvidencePacket.xaml.  Reads in 64 KB chunks to avoid loading the
    entire file into memory.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Get_RunContext.xaml
# ─────────────────────────────────────────────────────────────────────────────

def get_run_context() -> dict:
    """[ATLAS] Port of Get_RunContext.xaml.

    Collects execution-environment metadata that stamps every JSONL audit record
    in the run_context field.  Fields and fallback values are identical to the XAML:

        MachineName    → platform.node()            (≡ Environment.MachineName)
        UserName       → USERNAME / USER env var    (≡ Environment.UserName)
        RobotName      → env:RobotName or "unknown"
        ProcessName    → env:UIPATH_PROCESS_NAME or "unspecified"
        ProcessVersion → env:UIPATH_PROCESS_VERSION or "unspecified"
        JobId          → env:UIPATH_JOB_ID or new UUID
        Timestamp      → DateTime.UtcNow "o" format
    """
    return {
        "MachineName":    platform.node() or os.environ.get("COMPUTERNAME", "unknown"),
        "UserName":       os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "RobotName":      os.environ.get("RobotName", "unknown"),               # [ATLAS] exact env-var name
        "ProcessName":    os.environ.get("UIPATH_PROCESS_NAME", "unspecified"),
        "ProcessVersion": os.environ.get("UIPATH_PROCESS_VERSION", "unspecified"),
        "JobId":          os.environ.get("UIPATH_JOB_ID") or str(uuid.uuid4()),
        "Timestamp":      _utc_iso_o(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Redact_PII_Text.xaml
# ─────────────────────────────────────────────────────────────────────────────

# [ATLAS] Regex patterns copied verbatim from the InvokeCode block in
# Redact_PII_Text.xaml.  APPLICATION ORDER IS LOAD-BEARING — SSN before account
# prevents partial-digit false positives on card numbers that contain dashes.
# Do NOT reorder these tuples.
_PII_PATTERNS: list[tuple[str, str]] = [
    ("ssn",     r"\b\d{3}-\d{2}-\d{4}\b"),
    ("account", r"\b(?:\d[ -]*?){13,19}\b"),
    ("phone",   r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ("email",   r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
]

def redact_pii_text(
    input_text: str,
    redact_emails: bool = True,
    redact_phones: bool = True,
    redact_ssn: bool = True,
    redact_account_numbers: bool = True,
    replacement: str = "%[REDACTED]",
) -> dict:
    """[ATLAS] Port of Redact_PII_Text.xaml.

    Applies regex redaction in the fixed ATLAS order: SSN → account → phone → email.
    Only patterns whose flag is True and whose text is non-empty are run.
    A detected_type label is appended only when the pattern has ≥1 match
    (mirrors the XAML's `if (matches.Count > 0)` guard).

    Returns:
        redacted_text   : str   — input with PII tokens replaced
        redaction_count : int   — cumulative count across all pattern types
        detected_types  : list  — ordered list of type labels that had matches
    """
    flags = {
        "ssn":     redact_ssn,
        "account": redact_account_numbers,
        "phone":   redact_phones,
        "email":   redact_emails,
    }

    working: str = input_text or ""
    count: int = 0
    detected: list[str] = []

    for pii_type, pattern in _PII_PATTERNS:          # [ATLAS] order is contract
        if not flags[pii_type] or not working:
            continue
        matches = re.findall(pattern, working)
        if matches:
            working = re.sub(pattern, replacement, working)
            count += len(matches)
            detected.append(pii_type)

    return {
        "redacted_text":   working,
        "redaction_count": count,
        "detected_types":  detected,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Log_NIST_AuditEvent.xaml
# ─────────────────────────────────────────────────────────────────────────────

_AUDIT_SCHEMA_VERSION = "atlas.compliance.logging.v1"  # [ATLAS] in_SchemaVersion default

def log_nist_audit_event(
    event_type: str,
    control_ids: list,
    payload: dict,
    run_context: dict,
    output_path: str,
    redact_pii: bool = False,
    schema_version: str = _AUDIT_SCHEMA_VERSION,
) -> dict:
    """[ATLAS] Port of Log_NIST_AuditEvent.xaml.

    Appends one JSON line to output_path (creates parent dirs if needed).
    Record field order is canonical — matches XAML steps [6a]–[6g]:
        audit_event_id, written_at, event_type, control_ids,
        run_context, payload, schema_version

    The 'queue' and 'both' output targets are not implemented (ATLAS throws
    NotImplementedException for those; this port simply omits them — callers
    must use file output).

    Extra return key 'json_line' is a [FedClear] extension that exposes the
    serialised record string so the caller can feed it to hash_and_chain_audit
    without re-reading the file.
    """
    # [ATLAS] Generate event identity
    audit_event_id = str(uuid.uuid4())          # Guid.NewGuid().ToString()
    written_at = _utc_iso_o()                   # DateTime.UtcNow

    # [ATLAS] Fallback output path: CWD/audit.jsonl
    resolved_path = output_path or os.path.join(os.getcwd(), "audit.jsonl")

    # [ATLAS] Shallow copy of payload before optional redaction
    processed_payload: dict = dict(payload or {})

    if redact_pii:
        # [ATLAS] Serialize → Redact_PII_Text → deserialize
        # (mirrors the InvokeWorkflowFile(Redact_PII_Text.xaml) branch in the XAML)
        payload_json = json.dumps(processed_payload, ensure_ascii=False)
        result = redact_pii_text(payload_json)
        processed_payload = json.loads(result["redacted_text"])

    # [ATLAS] Audit record — field order matches XAML Assign steps [6a]–[6g]
    audit_record = {
        "audit_event_id": audit_event_id,           # [6a]
        "written_at":     written_at,               # [6b]
        "event_type":     event_type or "",         # [6c]
        "control_ids":    list(control_ids or []),  # [6d]
        "run_context":    run_context or {},        # [6e]
        "payload":        processed_payload,        # [6f]
        "schema_version": schema_version,           # [6g]
    }

    # [ATLAS] Formatting.None + Environment.NewLine  ≡  separators=(",",":") + "\n"
    json_line = json.dumps(audit_record, ensure_ascii=False, separators=(",", ":")) + "\n"

    # [ATLAS] Directory.CreateDirectory + File.AppendAllText
    os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)
    with open(resolved_path, "a", encoding="utf-8") as f:
        f.write(json_line)

    return {
        "audit_event_id": audit_event_id,
        "written_at":     written_at,
        "output_path":    resolved_path,
        "json_line":      json_line.rstrip("\n"),  # [FedClear] exposed for hash_and_chain_audit input
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Hash_And_Chain_Audit.xaml
# ─────────────────────────────────────────────────────────────────────────────

def hash_and_chain_audit(current_record: str, prev_hash: str = "") -> tuple[str, str]:
    """[ATLAS] Port of Hash_And_Chain_Audit.xaml.

    Both hashes are computed over UTF-8 encoded strings, producing 64-char
    lowercase hex — identical to the XAML's BitConverter/Replace/ToLowerInvariant.

        record_hash  = SHA-256( UTF-8(current_record) )
        chained_hash = SHA-256( UTF-8(prev_hash + current_record) )

    First record invariant (from XAML comment):
        prev_hash == "" → chained_hash == record_hash

    Returns (record_hash, chained_hash).
    """
    if not current_record:
        raise ValueError(
            "current_record cannot be null or empty. "
            "The hash chain requires a real audit record to hash."   # [ATLAS] exact error text
        )

    prev = prev_hash or ""  # [ATLAS] null-coalesce

    record_hash  = _sha256_hex(current_record.encode("utf-8"))              # [ATLAS] SHA-256(record alone)
    chained_hash = _sha256_hex((prev + current_record).encode("utf-8"))     # [ATLAS] SHA-256(prevHash + record)

    return record_hash, chained_hash


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Apply_Retention_Policy.xaml
# ─────────────────────────────────────────────────────────────────────────────

def apply_retention_policy(
    target_file_path: str,
    retention_class: str,
    retention_years: int,
    stamped_by: str = "",
) -> dict:
    """[ATLAS] Port of Apply_Retention_Policy.xaml.

    Writes a sidecar file at exactly '{target_file_path}.retention.json'
    (path appended verbatim — matches C# in_TargetFilePath + ".retention.json").
    Schema: atlas.compliance.retention.v1; NIST controls: AU-11, SI-12.

    Returns {sidecar_path, expiry_date}.
    """
    # [ATLAS] Input guards (mirrors the XAML validation block)
    if not target_file_path or not target_file_path.strip():
        raise ValueError("target_file_path is required.")
    if not retention_class or not retention_class.strip():
        raise ValueError("retention_class is required.")
    if retention_years <= 0:
        raise ValueError("retention_years must be greater than zero.")
    if not os.path.isfile(target_file_path):
        raise FileNotFoundError(f"Target file not found: {target_file_path}")

    # [ATLAS] Compute dates
    effective: datetime = datetime.now(timezone.utc)        # DateTime.UtcNow
    expiry: datetime    = _add_years(effective, retention_years)

    # [ATLAS] stamped_by fallback to Environment.UserName
    resolved_by: str = (
        stamped_by.strip()
        if stamped_by and stamped_by.strip()
        else (os.environ.get("USERNAME") or os.environ.get("USER") or "unknown")
    )

    # [ATLAS] Sidecar JSON — field order matches XAML JObject construction
    sidecar: dict = {
        "schema_version":  "atlas.compliance.retention.v1",
        "target_file":     os.path.basename(target_file_path),  # Path.GetFileName only
        "retention_class": retention_class,
        "retention_years": retention_years,
        "effective_date":  effective.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "expiry_date":     expiry.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "stamped_by":      resolved_by,
        "nist_controls":   ["AU-11", "SI-12"],                   # [ATLAS] hardcoded
    }

    # [ATLAS] File.WriteAllText (UTF-8, pretty-printed = Formatting.Indented)
    sidecar_path: str = target_file_path + ".retention.json"    # [ATLAS] appended verbatim
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)

    return {
        "sidecar_path": sidecar_path,
        "expiry_date":  expiry.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Build_AuditEvidencePacket.xaml
# ─────────────────────────────────────────────────────────────────────────────

def build_audit_evidence_packet(
    audit_log_path: str,
    output_zip_path: str,
    packet_id: str = "",
) -> dict:
    """[ATLAS] Port of Build_AuditEvidencePacket.xaml.

    Creates an atomic evidence ZIP containing the audit log and a manifest.json.
    Refuses to overwrite an existing ZIP (federal forensics atomic-creation rule).
    Manifest schema: atlas.compliance.evidence.v1; NIST controls: AU-4, AU-11, AU-12.

    Packet ID format when not supplied (mirrors C# implementation):
        ATLAS-PKT-{yyyyMMdd-HHmmss}-{GUID[0:8].upper()}

    Returns {packet_id, zip_path, manifest_json}.
    """
    # [ATLAS] Input guards
    if not audit_log_path or not audit_log_path.strip():
        raise ValueError("audit_log_path is required.")
    if not output_zip_path or not output_zip_path.strip():
        raise ValueError("output_zip_path is required.")
    if not os.path.isfile(audit_log_path):
        raise FileNotFoundError(f"Audit log not found: {audit_log_path}")
    if os.path.exists(output_zip_path):
        # [ATLAS] exact error semantics from the XAML
        raise FileExistsError(
            "Output ZIP already exists — federal forensics requires atomic packet creation: "
            + output_zip_path
        )

    # [ATLAS] Resolve or generate packet ID
    resolved_id: str = (
        packet_id.strip()
        if packet_id and packet_id.strip()
        else (
            "ATLAS-PKT-"
            + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + "-"
            + str(uuid.uuid4()).replace("-", "")[:8].upper()
        )
    )

    # [ATLAS] SHA-256 + byte count of the audit log (streaming, matches ComputeHash(FileStream))
    audit_log_hash:  str  = _sha256_file(audit_log_path)
    audit_log_bytes: int  = os.path.getsize(audit_log_path)

    # [ATLAS] manifest.json — Formatting.Indented, schema atlas.compliance.evidence.v1
    manifest: dict = {
        "schema_version": "atlas.compliance.evidence.v1",
        "packet_id":      resolved_id,
        "built_at":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "nist_controls":  ["AU-4", "AU-11", "AU-12"],          # [ATLAS] hardcoded
        "files": [
            {
                "name":   os.path.basename(audit_log_path),
                "bytes":  audit_log_bytes,
                "sha256": audit_log_hash,
            }
        ],
    }
    manifest_json: str = json.dumps(manifest, indent=2, ensure_ascii=False)

    # [ATLAS] ZipFile.CreateFromDirectory(..., CompressionLevel.Optimal, includeBaseDirectory=false)
    # Python equivalent: ZIP_DEFLATED + compresslevel=9, write each file with arcname only (no dir)
    os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(audit_log_path, arcname=os.path.basename(audit_log_path))
        zf.writestr("manifest.json", manifest_json)

    return {
        "packet_id":     resolved_id,
        "zip_path":      output_zip_path,
        "manifest_json": manifest_json,
    }
