"""Tests for DPDP Consent Management Platform."""
import os

# Set environment BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["API_KEY"] = "test-api-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base
from main import app, get_db

# Use StaticPool so all connections share the same in-memory database
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)
HEADERS = {"X-API-Key": "test-api-key"}


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# --- Health Check ---

class TestHealthCheck:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_no_auth_required(self):
        """Health endpoint should not require API key."""
        response = client.get("/health")
        assert response.status_code == 200


# --- Authentication ---

class TestAuthentication:
    def test_missing_api_key(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        })
        assert response.status_code == 403

    def test_invalid_api_key(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403

    def test_valid_api_key(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        assert response.status_code == 200


# --- Consent Grant ---

class TestConsentGrant:
    def test_grant_consent_success(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user1"
        assert data["purpose"] == "marketing"
        assert data["granted"] is True
        assert data["withdrawn_at"] is None
        assert "id" in data
        assert "granted_at" in data

    def test_grant_consent_with_metadata(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "analytics", "metadata": "campaign-2024"
        }, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"] == "campaign-2024"

    def test_grant_consent_empty_user_id(self):
        response = client.post("/consent", json={
            "user_id": "", "purpose": "marketing"
        }, headers=HEADERS)
        assert response.status_code == 422

    def test_grant_consent_empty_purpose(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "   "
        }, headers=HEADERS)
        assert response.status_code == 422

    def test_grant_consent_user_id_too_long(self):
        response = client.post("/consent", json={
            "user_id": "x" * 256, "purpose": "marketing"
        }, headers=HEADERS)
        assert response.status_code == 422

    def test_grant_consent_purpose_too_long(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "x" * 501
        }, headers=HEADERS)
        assert response.status_code == 422

    def test_grant_consent_idempotent_for_active(self):
        """Re-granting the same active (user_id, purpose) returns the same record."""
        first = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        second = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]

        # Only one active consent should exist.
        listing = client.get("/consent/user1", headers=HEADERS)
        assert len(listing.json()) == 1

    def test_regrant_after_withdrawal_creates_new(self):
        """After withdrawing, granting again creates a fresh active consent."""
        first = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        consent_id = first.json()["id"]
        client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)

        second = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        assert second.status_code == 200
        assert second.json()["id"] != consent_id
        assert second.json()["granted"] is True


# --- Get Consents ---

class TestGetConsents:
    def test_get_consents_empty(self):
        response = client.get("/consent/user1", headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_consents_returns_granted(self):
        client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        client.post("/consent", json={
            "user_id": "user1", "purpose": "analytics"
        }, headers=HEADERS)

        response = client.get("/consent/user1", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_consents_pagination(self):
        for i in range(5):
            client.post("/consent", json={
                "user_id": "user1", "purpose": f"purpose-{i}"
            }, headers=HEADERS)

        response = client.get("/consent/user1?limit=2&offset=0", headers=HEADERS)
        assert len(response.json()) == 2

        response = client.get("/consent/user1?limit=2&offset=3", headers=HEADERS)
        assert len(response.json()) == 2

    def test_get_consents_different_users(self):
        client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        client.post("/consent", json={
            "user_id": "user2", "purpose": "analytics"
        }, headers=HEADERS)

        response = client.get("/consent/user1", headers=HEADERS)
        assert len(response.json()) == 1
        assert response.json()[0]["user_id"] == "user1"

    def test_get_consents_invalid_user_id_special_chars(self):
        response = client.get("/consent/user<script>", headers=HEADERS)
        assert response.status_code == 400

    def test_get_consents_limit_too_high(self):
        response = client.get("/consent/user1?limit=1001", headers=HEADERS)
        assert response.status_code == 422

    def test_get_consents_limit_zero(self):
        response = client.get("/consent/user1?limit=0", headers=HEADERS)
        assert response.status_code == 422

    def test_get_consents_negative_offset(self):
        response = client.get("/consent/user1?offset=-1", headers=HEADERS)
        assert response.status_code == 422


# --- Consent Withdrawal ---

class TestConsentWithdraw:
    def _grant_consent(self):
        response = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        return response.json()["id"]

    def test_withdraw_consent_success(self):
        consent_id = self._grant_consent()
        response = client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["message"] == "Consent withdrawn successfully"

    def test_withdraw_consent_not_found(self):
        response = client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": "00000000-0000-0000-0000-000000000000"
        }, headers=HEADERS)
        assert response.status_code == 404

    def test_double_withdrawal_rejected(self):
        consent_id = self._grant_consent()
        # First withdrawal
        client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)
        # Second withdrawal should fail
        response = client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)
        assert response.status_code == 404

    def test_withdraw_wrong_user(self):
        consent_id = self._grant_consent()
        response = client.post("/consent/withdraw", json={
            "user_id": "user2", "consent_id": consent_id
        }, headers=HEADERS)
        assert response.status_code == 404

    def test_withdraw_invalid_uuid(self):
        response = client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": "not-a-uuid"
        }, headers=HEADERS)
        assert response.status_code == 422

    def test_consent_shows_withdrawn_after_withdrawal(self):
        consent_id = self._grant_consent()
        client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)

        response = client.get("/consent/user1", headers=HEADERS)
        consent = response.json()[0]
        assert consent["granted"] is False
        assert consent["withdrawn_at"] is not None


# --- Audit Logs ---

class TestAuditLogs:
    def test_audit_log_on_grant(self):
        client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)

        response = client.get("/audit/user1", headers=HEADERS)
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 1
        assert logs[0]["action"] == "CONSENT_GRANTED"
        assert logs[0]["user_id"] == "user1"
        assert "marketing" in logs[0]["details"]

    def test_audit_log_on_withdraw(self):
        # Grant first
        grant_resp = client.post("/consent", json={
            "user_id": "user1", "purpose": "marketing"
        }, headers=HEADERS)
        consent_id = grant_resp.json()["id"]

        # Withdraw
        client.post("/consent/withdraw", json={
            "user_id": "user1", "consent_id": consent_id
        }, headers=HEADERS)

        response = client.get("/audit/user1", headers=HEADERS)
        logs = response.json()
        assert len(logs) == 2
        actions = [log["action"] for log in logs]
        assert "CONSENT_GRANTED" in actions
        assert "CONSENT_WITHDRAWN" in actions

    def test_audit_logs_pagination(self):
        for i in range(5):
            client.post("/consent", json={
                "user_id": "user1", "purpose": f"purpose-{i}"
            }, headers=HEADERS)

        response = client.get("/audit/user1?limit=2&offset=0", headers=HEADERS)
        assert len(response.json()) == 2

    def test_audit_logs_empty(self):
        response = client.get("/audit/user1", headers=HEADERS)
        assert response.status_code == 200
        assert response.json() == []

    def test_audit_logs_invalid_user_id(self):
        response = client.get("/audit/user%3Cscript%3E", headers=HEADERS)
        assert response.status_code == 400
