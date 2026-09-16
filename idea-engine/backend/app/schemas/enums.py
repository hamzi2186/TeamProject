from enum import Enum


class Direction(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class Channel(str, Enum):
    CALL = "CALL"
    SMS = "SMS"
    EMAIL = "EMAIL"


class LeadOutcome(str, Enum):
    NEW = "NEW"
    CONTACTING = "CONTACTING"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    NO_ANSWER = "NO_ANSWER"
    NO_RESPONSE = "NO_RESPONSE"
    CONVERTED = "CONVERTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
