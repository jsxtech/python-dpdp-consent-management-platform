import logging
import secrets
import uuid
import os
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Depends, Path, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models import SessionLocal, Consent, AuditLog, Base, engine, utc_now
from schemas import (
    ConsentCreate,
    ConsentResponse,
    ConsentWithdraw,
    AuditLogResponse,
    WithdrawResponse,
    USER_ID_PATTERN,
)

logger = logging.getLogger(__name__)

DEFAULT_API_KEY = "dev-key-change-in-production"
API_KEY = os.getenv("API_KEY", DEFAULT_API_KEY)
APP_ENV = os.getenv("APP_ENV", "development").lower()

if API_KEY == DEFAULT_API_KEY:
    if APP_ENV in ("production", "prod"):
        raise RuntimeError(
            "API_KEY is set to the default development key in a production "
            "environment. Set a strong API_KEY before starting the server."
        )
    logger.warning(
        "Using the default development API key. Set the API_KEY environment "
        "variable to a strong secret before deploying."
    )

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
    yield


app = FastAPI(title="DPDP Consent Management Platform", lifespan=lifespan)

# CORS configuration
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
# Browsers forbid credentialed requests with a wildcard origin, and it is a
# security footgun. Refuse to start with that combination.
if "*" in _cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS cannot contain '*' when credentials are allowed. "
        "List explicit origins instead."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


def verify_api_key(api_key: str = Security(api_key_header)):
    # secrets.compare_digest raises TypeError on strings containing non-ASCII
    # characters. Compare on the UTF-8 byte representation so a malformed
    # header yields a clean 403 instead of an unhandled 500.
    provided = api_key.encode("utf-8")
    expected = API_KEY.encode("utf-8")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


def validate_path_user_id(user_id: str) -> str:
    """Validate user_id path parameter to prevent path traversal and injection."""
    if not user_id or len(user_id) > 255:
        raise HTTPException(status_code=400, detail="Invalid user_id")
    if not USER_ID_PATTERN.match(user_id):
        raise HTTPException(status_code=400, detail="user_id contains invalid characters")
    return user_id


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_audit(db: Session, user_id: str, action: str, details: str = None):
    log = AuditLog(id=str(uuid.uuid4()), user_id=user_id, action=action, details=details)
    db.add(log)


@app.get("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy"}


@app.post("/consent", response_model=ConsentResponse)
def grant_consent(consent: ConsentCreate, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    try:
        # Idempotency: if an active consent already exists for this
        # (user_id, purpose), return it instead of creating a duplicate.
        existing = db.query(Consent).filter(
            Consent.user_id == consent.user_id,
            Consent.purpose == consent.purpose,
            Consent.granted == True,
        ).first()
        if existing:
            return existing

        new_consent = Consent(
            id=str(uuid.uuid4()),
            user_id=consent.user_id,
            purpose=consent.purpose,
            consent_metadata=consent.metadata
        )
        db.add(new_consent)
        log_audit(db, consent.user_id, "CONSENT_GRANTED", f"Purpose: {consent.purpose}")
        db.commit()
        db.refresh(new_consent)
        return new_consent
    except IntegrityError:
        # Concurrent insert raced past the pre-check and hit the unique index.
        db.rollback()
        existing = db.query(Consent).filter(
            Consent.user_id == consent.user_id,
            Consent.purpose == consent.purpose,
            Consent.granted == True,
        ).first()
        if existing:
            return existing
        logger.exception("Integrity error in grant_consent")
        raise HTTPException(status_code=409, detail="Consent conflict")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in grant_consent")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception:
        db.rollback()
        logger.exception("Unexpected error in grant_consent")
        raise


@app.get("/consent/{user_id}", response_model=List[ConsentResponse])
def get_consents(
    user_id: str = Path(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key),
):
    user_id = validate_path_user_id(user_id)
    consents = db.query(Consent).filter(
        Consent.user_id == user_id
    ).order_by(Consent.granted_at.desc(), Consent.id.desc()).limit(limit).offset(offset).all()
    return consents


@app.post("/consent/withdraw", response_model=WithdrawResponse)
def withdraw_consent(withdraw: ConsentWithdraw, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    try:
        consent = db.query(Consent).filter(
            Consent.id == withdraw.consent_id,
            Consent.user_id == withdraw.user_id,
            Consent.granted == True
        ).first()

        if not consent:
            raise HTTPException(status_code=404, detail="Consent not found or already withdrawn")

        consent.granted = False
        consent.withdrawn_at = utc_now()
        log_audit(db, withdraw.user_id, "CONSENT_WITHDRAWN", f"Consent ID: {withdraw.consent_id}")
        db.commit()
        return {"message": "Consent withdrawn successfully"}
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in withdraw_consent")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception:
        db.rollback()
        logger.exception("Unexpected error in withdraw_consent")
        raise


@app.get("/audit/{user_id}", response_model=List[AuditLogResponse])
def get_audit_logs(
    user_id: str = Path(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key),
):
    user_id = validate_path_user_id(user_id)
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == user_id
    ).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).limit(limit).offset(offset).all()
    return logs
