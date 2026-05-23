"""
FedClear triage agent — AgentHack 2026, Track 1 (Maestro Case).
Built via Claude Code. Maps ATO findings to routing decisions using
NIST 800-53 control confidence scores and the five core routing rules.
All findings are synthetic; no real agency data is processed here.
"""

import json
import pathlib

CONFIDENCE_THRESHOLD = 0.65
HIGH_SEVERITY_LEVELS = {"Critical", "High"}

FINDINGS_PATH = pathlib.Path(__file__).parent.parent / "mock-data" / "findings.json"
REPORT_PATH = pathlib.Path(__file__).parent / "triage_report.json"


def _expected_from_notes(notes: str) -> str:
    n = notes.lower()
    if "auto-clear" in n:
        return "auto_clear"
    if "mandatory human sign-off" in n:
        return "escalate_high_severity"
    if "escalate as ambiguous" in n:
        return "escalate_ambiguous_mapping"
    if "request more evidence" in n:
        return "request_more_evidence"
    # Notes that open with "Ambiguous (...)" and close with plain "escalate"
    # still imply an ambiguous-mapping escalation.
    if "ambiguous" in n and "escalate" in n:
        return "escalate_ambiguous_mapping"
    if "escalate" in n:
        return "escalate_low_confidence"
    return "unknown"


def triage(finding: dict) -> tuple[str, str]:
    """Return (agent_decision, reasoning) for a single finding.

    Priority order mirrors the five rules in CLAUDE.md:
    1. Missing evidence (empty evidence_refs)
    2. Ambiguous NIST mapping (alternate_controls present)
    3. High/Critical severity — mandatory sign-off regardless of confidence
    4. Low confidence on either score — escalate to reviewer
    5. Auto-clear (both scores high, low/medium severity)
    """
    severity = finding["severity_hint"]
    evidence_refs = finding["evidence_refs"]
    ci = finding["confidence_inputs"]
    scanner_conf = ci["scanner_confidence"]
    match_score = ci["control_match_score"]
    alternates = ci.get("alternate_controls", [])

    # Rule 5 (checked first as a base condition): missing evidence
    if not evidence_refs:
        return (
            "request_more_evidence",
            "Evidence package is empty; cannot validate without supporting artifacts.",
        )

    # Rule 4: ambiguous NIST mapping — alternate controls with no clear winner
    if alternates:
        return (
            "escalate_ambiguous_mapping",
            f"Mapping is ambiguous across {len(alternates) + 1} controls "
            f"({finding['suggested_nist_control']} vs {', '.join(alternates)}); "
            "human judgement required.",
        )

    # Rule 3: mandatory sign-off for High/Critical severity
    if severity in HIGH_SEVERITY_LEVELS:
        return (
            "escalate_high_severity",
            f"{severity}-severity finding requires mandatory human sign-off "
            "regardless of confidence scores.",
        )

    # Rule 2: either confidence score below threshold
    if scanner_conf < CONFIDENCE_THRESHOLD or match_score < CONFIDENCE_THRESHOLD:
        low_scores = [
            f"scanner_confidence={scanner_conf:.2f}" if scanner_conf < CONFIDENCE_THRESHOLD else None,
            f"control_match_score={match_score:.2f}" if match_score < CONFIDENCE_THRESHOLD else None,
        ]
        label = ", ".join(s for s in low_scores if s)
        return (
            "escalate_low_confidence",
            f"Confidence below {CONFIDENCE_THRESHOLD} threshold ({label}); escalating to reviewer.",
        )

    # Rule 1: auto-clear — high confidence, low/medium severity
    return (
        "auto_clear",
        f"Both confidence scores exceed threshold "
        f"(scanner={scanner_conf:.2f}, match={match_score:.2f}) "
        f"and severity is {severity}; agent resolves.",
    )


def run() -> None:
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))

    report = []
    decision_counts: dict[str, int] = {}

    for f in findings:
        decision, reasoning = triage(f)
        expected = _expected_from_notes(f.get("_notes", ""))
        matches = decision == expected

        report.append(
            {
                "id": f["id"],
                "finding_type": f["finding_type"],
                "agent_decision": decision,
                "reasoning": reasoning,
                "matches_expected": matches,
            }
        )
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = len(report)
    correct = sum(1 for r in report if r["matches_expected"])
    accuracy = correct / total * 100

    print("FedClear Triage Agent - Run complete")
    print("-" * 45)
    print(f"Total findings processed : {total}")
    print(f"")
    print(f"Decisions by category:")
    for decision, count in sorted(decision_counts.items()):
        print(f"  {decision:<35} {count:>3}")
    print(f"")
    print(f"Accuracy (vs _notes expected) : {correct}/{total}  ({accuracy:.1f}%)")
    print(f"Report written to            : {REPORT_PATH.resolve()}")

    mismatches = [r for r in report if not r["matches_expected"]]
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for r in mismatches:
            print(f"  {r['id']}: got={r['agent_decision']}")


if __name__ == "__main__":
    run()
