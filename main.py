from fastapi import FastAPI, HTTPException, Depends, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import uuid
import os
from models import SessionLocal, Consent, AuditLog, utc_now
from schemas import ConsentCreate, ConsentResponse, ConsentWithdraw

app = FastAPI(title="DPDP Consent Management Platform")

API_KEY = os.getenv("API_KEY", "dev-key-change-in-production")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_audit(db: Session, user_id: str, action: str, details: str = None):
    log = AuditLog(id=str(uuid.uuid4()), user_id=user_id, action=action, details=details)
    db.add(log)

@app.post("/consent", response_model=ConsentResponse)
def grant_consent(consent: ConsentCreate, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    try:
        new_consent = Consent(
            id=str(uuid.uuid4()),
            user_id=consent.user_id,
            purpose=consent.purpose,
            metadata=consent.metadata
        )
        db.add(new_consent)
        log_audit(db, consent.user_id, "CONSENT_GRANTED", f"Purpose: {consent.purpose}")
        db.commit()
        db.refresh(new_consent)
        return new_consent
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
    except Exception:
        db.rollback()
        raise

@app.get("/consent/{user_id}")
def get_consents(
    user_id: str, 
    db: Session = Depends(get_db),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key)
):
    consents = db.query(Consent).filter(
        Consent.user_id == user_id
    ).order_by(Consent.granted_at.desc()).limit(limit).offset(offset).all()
    return consents

@app.post("/consent/withdraw")
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
        raise HTTPException(status_code=500, detail="Database error")
    except Exception:
        db.rollback()
        raise

@app.get("/audit/{user_id}")
def get_audit_logs(
    user_id: str, 
    db: Session = Depends(get_db),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key)
):
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == user_id
    ).order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()
    return logs
