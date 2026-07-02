"""Streamlit UI for ComplyAgent.

Run with:
    uv run streamlit run app.py

Paste a privacy policy, choose audit mode, watch live progress, see the report.
"""

from pathlib import Path
from typing import Literal

import streamlit as st

from complyagent.supervisor.events import AuditCompleteEvent, AuditEvent
from complyagent.supervisor.run_audit import stream_audit



# --- Page setup --------------------------------------------------------------

st.set_page_config(
    page_title="ComplyAgent — GDPR Compliance Auditor",
    page_icon="📋",
    layout="wide",
)

st.title("ComplyAgent")
st.caption("Multi-agent GDPR compliance auditor")


# --- Synthetic policy presets -----------------------------------------------

SYNTHETIC_DIR = Path("data/policies/synthetic")
PRESETS = {
    "Policy A — mostly compliant": "policy_a_mostly_compliant.txt",
    "Policy B — subtle gaps": "policy_b_subtle_gaps.txt",
    "Policy C — egregious violations": "policy_c_egregious_violations.txt",
}


def _load_preset(filename: str) -> str:
    """Load a synthetic policy from disk."""
    return (SYNTHETIC_DIR / filename).read_text(encoding="utf-8")


# --- Session state -----------------------------------------------------------
# Streamlit "owns" widget values through their `key=`. To programmatically
# update a widget from a button (e.g. preset → textarea), we write to the
# widget's session_state key directly *before* the widget renders.
#
# So: the textarea uses key="policy_input", and preset buttons write to
# st.session_state.policy_input. The widget reads from session_state.policy_input
# on the next render — no separate "policy_text" intermediate.

if "policy_input" not in st.session_state:
    st.session_state.policy_input = ""

if "audit_mode" not in st.session_state:
    st.session_state.audit_mode = "full_policy"

if "final_report" not in st.session_state:
    st.session_state.final_report = None


# --- Sidebar: presets + audit mode -------------------------------------------

with st.sidebar:
    st.header("Setup")

    st.subheader("Try a synthetic policy")
    for label, filename in PRESETS.items():
        if st.button(label, use_container_width=True):
            st.session_state.policy_input = _load_preset(filename)
            st.session_state.final_report = None  # clear stale report
            st.rerun()  # force immediate rerender so textarea picks up new value
    
    st.divider()

    st.subheader("Audit mode")
    mode_label = st.radio(
        "How should we audit this?",
        options=["Full policy (Case 2)", "Single clause (Case 1)"],
        index=0 if st.session_state.audit_mode == "full_policy" else 1,
        help=(
            "Full policy: per-statement compliance check + coverage-gap analysis. "
            "Single clause: per-statement compliance check only (no gap analysis)."
        ),
    )
    st.session_state.audit_mode = (
        "full_policy" if mode_label.startswith("Full") else "single_clause"
    )


# --- Main panel: input + run button -----------------------------------------

st.subheader("Privacy policy text")

uploaded_file = st.file_uploader(
    "Upload a .txt policy file, or paste below.",
    type=["txt"],
    accept_multiple_files=False,
    help="Plain text files only. Upload populates the textarea below.",
)
if uploaded_file is not None:
    # When a file is uploaded, push its contents into the textarea's
    # session_state key. Streamlit re-renders and the textarea picks it up.
    try:
        file_contents = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        st.error("Could not decode the file as UTF-8. Please upload a plain text file.")
        st.stop()
    if file_contents != st.session_state.get("policy_input", ""):
        # Only update if the content is genuinely different — avoids
        # an infinite re-render loop on Streamlit's automatic uploader behavior.
        st.session_state.policy_input = file_contents
        st.session_state.final_report = None  # clear stale report
        st.rerun()

policy_input = st.text_area(
    "Paste the policy text here, upload a file above, or use a preset from the sidebar.",
    height=300,
    key="policy_input",
)

run_clicked = st.button(
    "Run audit",
    type="primary",
    disabled=not policy_input.strip(),
    use_container_width=True,
)


# --- Audit run with live progress -------------------------------------------

def _phase_label(phase: str) -> str:
    """Human-readable phase name for the progress feed."""
    return {
        "parser": "Parsing policy",
        "process_statement": "Researching + analyzing statement",
        "check_confidence": "Checking finding confidence",
        "route": "Routing audit path",
        "gap_hunter": "Hunting coverage gaps",
        "remediation": "Drafting remediations",
        "report_writer": "Writing report",
    }.get(phase, phase)


if run_clicked:
    # Defensive check: textarea allowed click only when non-blank, but a textarea
    # containing only whitespace and newlines slips past .strip() == "" for the
    # button disable but still has no real content. Guard explicitly.
    if len(policy_input.strip()) < 5:
        st.warning(
            "The policy text is empty or too short. Paste a policy or load a preset from the sidebar."
        )
        st.stop()
    
    st.session_state.final_report = None  # clear any previous run

    progress_placeholder = st.empty()
    feed_placeholder = st.empty()
    feed_entries: list[str] = []

    audit_mode: Literal["single_clause", "full_policy"] = st.session_state.audit_mode

    try:
        for event in stream_audit(
            raw_policy_text=policy_input,
            audit_mode=audit_mode,
            policy_source="streamlit-pasted-input",
        ):
            if isinstance(event, AuditEvent):
                # Format a one-line feed entry. Decision reasoning is the
                # most useful payload — it carries the supervisor's actual
                # thinking, not just a static "step done" message.
                label = _phase_label(event.phase)
                if event.decision is not None:
                    feed_entries.append(f"**{label}** — {event.decision.reasoning}")
                else:
                    feed_entries.append(f"**{label}** — done")

                # Render the running feed as one combined markdown block.
                # Using .markdown() on an st.empty() placeholder REPLACES its
                # contents each call — unlike st.container(), which stacks a
                # new nested container on every call, causing visual duplication.
                feed_placeholder.markdown(
                    "\n".join(f"- {line}" for line in feed_entries)
                )

                stats = event.stats
                progress_placeholder.info(
                    f"Statements: {stats.get('statements', 0)} · "
                    f"Findings: {stats.get('findings', 0)} · "
                    f"Gaps: {stats.get('gaps', 0)} · "
                    f"Remediations: {stats.get('remediations', 0)}"
                )

            elif isinstance(event, AuditCompleteEvent):
                st.session_state.final_report = event.report

        progress_placeholder.success("Audit complete.")

    except Exception as e:
        st.error(f"Audit failed: {type(e).__name__}: {e}")
        # Show the partial feed for diagnostic value.
        with feed_placeholder.container():
            for line in feed_entries:
                st.markdown(f"- {line}")


# --- Final report display ----------------------------------------------------

if st.session_state.final_report is not None:
    report = st.session_state.final_report

    st.divider()
    st.subheader("Audit report")

    # --- Top-of-report metrics ----------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Statements", len(report.statements))
    col2.metric("Findings", len(report.findings))
    col3.metric("Gaps", len(report.gaps))
    col4.metric("Remediations", len(report.remediations))

    # --- About this audit ---------------------------------------------------
    with st.expander("About this audit"):
        # Render audit metadata in a key/value grid.
        # audit_mode is read from session_state because it's not preserved on
        # AuditReport itself — but for demo reports, we surface the source label
        # which is enough orientation.
        info_col1, info_col2 = st.columns(2)
        info_col1.markdown(f"**Audit ID:** `{report.audit_id}`")
        info_col1.markdown(f"**Policy source:** {report.policy_source}")
        info_col2.markdown(
            f"**Created at:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        info_col2.markdown(f"**Total decisions logged:** {len(report.decisions)}")

    # --- Verdict breakdown ---------------------------------------------------
    verdict_counts = {"compliant": 0, "partial": 0, "violation": 0, "unclear": 0}
    for f in report.findings:
        verdict_counts[f.verdict.value] += 1

    st.markdown("##### Verdict breakdown")
    vc1, vc2, vc3, vc4 = st.columns(4)
    vc1.markdown(f"🟢 **Compliant:** {verdict_counts['compliant']}")
    vc2.markdown(f"🟡 **Partial:** {verdict_counts['partial']}")
    vc3.markdown(f"🔴 **Violation:** {verdict_counts['violation']}")
    vc4.markdown(f"⚪ **Unclear:** {verdict_counts['unclear']}")

    # --- Executive summary ---------------------------------------------------
    st.markdown("##### Executive summary")
    st.info(report.executive_summary)

    # --- Findings (one expandable per finding) -------------------------------
    if report.findings:
        st.markdown("##### Findings")
        # Map statement_id to its text for inline display in each expander.
        stmt_text = {s.statement_id: s.text for s in report.statements}

        verdict_emoji = {
            "compliant": "🟢",
            "partial": "🟡",
            "violation": "🔴",
            "unclear": "⚪",
        }

        # Sort findings: violations first, then partial, then unclear, then compliant.
        verdict_order = {"violation": 0, "partial": 1, "unclear": 2, "compliant": 3}
        sorted_findings = sorted(
            report.findings,
            key=lambda f: verdict_order.get(f.verdict.value, 99),
        )

        for f in sorted_findings:
            emoji = verdict_emoji.get(f.verdict.value, "•")
            header = f"{emoji} [{f.statement_id}] {f.verdict.value.upper()} (confidence {f.confidence:.2f})"
            with st.expander(header):
                st.markdown(f"**Statement:** {stmt_text.get(f.statement_id, '(text unavailable)')}")
                st.markdown(f"**Rationale:** {f.rationale}")
                if f.citations:
                    st.markdown(f"**Citations:** {', '.join(f.citations)}")
                else:
                    st.markdown("**Citations:** _none_")

    # --- Gaps ----------------------------------------------------------------
    if report.gaps:
        st.markdown("##### Coverage gaps")

        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}
        severity_order = {"critical": 0, "high": 1, "medium": 2}
        sorted_gaps = sorted(
            report.gaps, key=lambda g: severity_order.get(g.severity.value, 99)
        )

        for g in sorted_gaps:
            emoji = severity_emoji.get(g.severity.value, "•")
            header = f"{emoji} [{g.gap_id}] {g.severity.value.upper()} — {g.requirement[:80]}"
            with st.expander(header):
                st.markdown(f"**Requirement:** {g.requirement}")
                st.markdown(f"**Rationale:** {g.rationale}")
                st.markdown(f"**GDPR basis:** {', '.join(g.gdpr_basis)}")

    # --- Remediations --------------------------------------------------------
    if report.remediations:
        st.markdown("##### Remediations")

        for r in report.remediations:
            target_emoji = "🔴" if r.target_kind == "finding" else "🟠"
            header = (
                f"{target_emoji} [{r.remediation_id}] for "
                f"{r.target_kind} {r.target_id}"
            )
            with st.expander(header):
                st.markdown(f"**Recommendation:** {r.recommendation}")
                st.markdown("**Suggested policy text:**")
                # Render in a quoted code block so multi-paragraph text reads
                # like a policy excerpt, not a wall of plain prose.
                st.markdown(f"> {r.suggested_policy_text}")
                if r.related_citations:
                    st.markdown(f"**Related citations:** {', '.join(r.related_citations)}")

    # --- Reasoning log (collapsed by default) --------------------------------
    if report.decisions:
        st.markdown("##### Reasoning log")
        with st.expander(f"Show {len(report.decisions)} supervisor decision(s)"):
            for d in report.decisions:
                terminal_marker = " ⚐" if d.is_terminal else ""
                st.markdown(
                    f"**Step {d.iteration}**{terminal_marker} "
                    f"({d.timestamp.strftime('%H:%M:%S')}): {d.reasoning}"
                )

    # --- Full markdown report (fallback for copy/paste) ---------------------
    with st.expander("Full markdown report (for copy/paste)"):
        st.markdown(report.markdown_report)
        st.divider()
        st.markdown("###### Raw markdown source")
        st.code(report.markdown_report, language="markdown")