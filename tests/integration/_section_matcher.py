"""Helpers for matching documented violations/gaps against audit outputs.

Sidecar JSON files describe expected violations by `section` name (e.g.
"WHAT WE DO WITH IT"). The Parser extracts statements without explicit
section attribution, so we re-derive section membership at test time by
finding which section header precedes each statement's source_span in the
original policy text.
"""

from __future__ import annotations

import re
from complyagent.schemas.findings import Finding
from complyagent.schemas.policy import PolicyStatement


# All-caps lines of 2+ words (allowing spaces, &, -, /) treated as headers.
# E.g. "WHAT WE COLLECT", "HOW LONG WE KEEP IT", "INTERNATIONAL TRANSFERS".
_HEADER_PATTERN = re.compile(r"^([A-Z][A-Z &/\-]{2,})\s*$", re.MULTILINE)


def split_into_sections(policy_text: str) -> dict[str, str]:
    """Return {section_header: section_body_text} for a policy with all-caps headers."""
    sections: dict[str, str] = {}
    matches = list(_HEADER_PATTERN.finditer(policy_text))

    for i, match in enumerate(matches):
        header = match.group(1).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(policy_text)
        sections[header] = policy_text[body_start:body_end].strip()

    return sections


def statements_for_section(
    statements: list[PolicyStatement],
    section_body: str,
) -> list[PolicyStatement]:
    """Return statements whose source_span appears within the section body."""
    matched = []
    for stmt in statements:
        if stmt.source_span and stmt.source_span.strip() in section_body:
            matched.append(stmt)
            continue
        # Fallback: substring match on a key fragment of the statement text.
        # Source_span may be slightly normalized; do a lenient check.
        if stmt.source_span:
            fragment = stmt.source_span.strip()[:50]
            if fragment and fragment in section_body:
                matched.append(stmt)
    return matched


def violation_caught(
    section_name: str,
    policy_text: str,
    statements: list[PolicyStatement],
    findings: list[Finding],
) -> bool:
    """A violation is 'caught' if any statement from the named section got a
    Finding with verdict in {violation, partial}.
    """
    sections = split_into_sections(policy_text)

    # Find the matching section header. Sidecar names may differ slightly in
    # spacing/punctuation, so do a fuzzy match (uppercase, strip non-alnum).
    def normalize(s: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", s.upper())

    section_body = None
    target = normalize(section_name)
    for header, body in sections.items():
        if normalize(header) == target:
            section_body = body
            break

    if section_body is None:
        return False

    section_statements = statements_for_section(statements, section_body)
    section_stmt_ids = {s.statement_id for s in section_statements}

    for finding in findings:
        if finding.statement_id in section_stmt_ids and finding.verdict.value in {"violation", "partial"}:
            return True

    return False