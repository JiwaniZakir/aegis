"""SQLAlchemy models — import all for Alembic autogenerate discovery."""

from app.models.account import Account
from app.models.assignment import Assignment
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.briefing import DailyBriefing
from app.models.contact import Contact, ContactEdge
from app.models.content import ContentPost
from app.models.credential import Credential
from app.models.email_digest import EmailDigest
from app.models.health import HealthMetric
from app.models.meeting import Meeting
from app.models.productivity import ProductivityLog
from app.models.transaction import Transaction
from app.models.user import User
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage

__all__ = [
    "Account",
    "Assignment",
    "AuditLog",
    "Base",
    "Contact",
    "ContactEdge",
    "ContentPost",
    "Credential",
    "DailyBriefing",
    "EmailDigest",
    "HealthMetric",
    "Meeting",
    "ProductivityLog",
    "Transaction",
    "User",
    "WhatsAppConversation",
    "WhatsAppMessage",
]
