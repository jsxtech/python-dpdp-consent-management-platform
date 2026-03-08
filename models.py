import os
from sqlalchemy import Column, String, DateTime, Boolean, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

def utc_now():
    return datetime.now(timezone.utc)

class Consent(Base):
    __tablename__ = "consents"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False)
    granted = Column(Boolean, default=True)
    granted_at = Column(DateTime, default=utc_now)
    withdrawn_at = Column(DateTime, nullable=True)
    metadata = Column(Text, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utc_now)
    details = Column(Text, nullable=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dpdp_consent.db")
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
