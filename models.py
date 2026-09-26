import os
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
    create_engine,
    true,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class Consent(Base):
    __tablename__ = "consents"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False)
    granted = Column(Boolean, nullable=False, default=True, server_default=true())
    granted_at = Column(DateTime(timezone=True), default=utc_now)
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    consent_metadata = Column("extra_metadata", Text, nullable=True)

    __table_args__ = (
        # Only one active (granted) consent per (user_id, purpose).
        # Uses a PARTIAL unique index so withdrawn rows do not count toward the
        # constraint, allowing a user to re-grant a purpose after withdrawal.
        #
        # NOTE: partial indexes are supported by SQLite and PostgreSQL only.
        # MySQL does not support them, so on MySQL this DB-level guarantee is
        # NOT enforced (a plain unique index would wrongly block re-granting a
        # previously withdrawn purpose). On MySQL, uniqueness of active consents
        # relies solely on the application-level check in grant_consent().
        Index(
            "uq_active_consent",
            "user_id",
            "purpose",
            unique=True,
            sqlite_where=(granted == True),
            postgresql_where=(granted == True),
        ),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    details = Column(Text, nullable=True)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dpdp_consent.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine)
