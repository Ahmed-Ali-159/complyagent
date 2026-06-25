"""Enums for typed categorical fields across schemas."""
from enum import Enum


class VerdictType(str, Enum):
    """Compliance verdict for a single PolicyStatement."""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    VIOLATION = "violation"
    UNCLEAR = "unclear"


class WorkerName(str, Enum):
    """The six worker agents the supervisor can dispatch to."""
    POLICY_PARSER = "policy_parser"
    REGULATION_RESEARCHER = "regulation_researcher"
    COMPLIANCE_ANALYST = "compliance_analyst"
    GAP_HUNTER = "gap_hunter"
    REMEDIATION_DRAFTER = "remediation_drafter"
    REPORT_WRITER = "report_writer"


class StatementCategory(str, Enum):
    """High-level topic of a policy statement — helps the supervisor route research queries."""
    DATA_COLLECTION = "data_collection"
    DATA_USE = "data_use"
    DATA_SHARING = "data_sharing"
    RETENTION = "retention"
    USER_RIGHTS = "user_rights"
    SECURITY = "security"
    INTERNATIONAL_TRANSFER = "international_transfer"
    CHILDREN = "children"
    COOKIES = "cookies"
    LEGAL_BASIS = "legal_basis"
    CONTACT = "contact"
    OTHER = "other"


class GapSeverity(str, Enum):
    """Severity of a missing GDPR requirement."""
    CRITICAL = "critical"  # mandatory disclosure / safeguard absent
    HIGH = "high"          # required by GDPR but ambiguously addressed
    MEDIUM = "medium"      # best practice gap