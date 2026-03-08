# DPDP Consent Management Platform

Minimal Python platform for DPDP Act 2023 compliance with consent management, audit trails, and API key authentication.

## Features

- ✅ **Consent Collection** - Record user consent with purpose specification
- ✅ **Consent Withdrawal** - Easy withdrawal mechanism with audit logging
- ✅ **Audit Trail** - Immutable logs for compliance verification
- ✅ **API Key Authentication** - Secure endpoints with configurable API keys
- ✅ **Input Validation** - Prevents empty/malicious data
- ✅ **Pagination** - Efficient data retrieval with limits
- ✅ **Transaction Safety** - Automatic rollback on errors
- ✅ **Timezone-aware Timestamps** - UTC timestamps for all records
- ✅ **Configurable Database** - SQLite default, supports PostgreSQL/MySQL
- ✅ **Prevents Double-withdrawal** - Validates consent state before withdrawal

## Tech Stack

- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - ORM with modern patterns
- **Pydantic 2.x** - Data validation
- **SQLite** - Default database (configurable)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export API_KEY="your-secret-api-key"
export DATABASE_URL="sqlite:///dpdp_consent.db"  # optional
```

## Run

```bash
uvicorn main:app --reload
```

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Authentication

All endpoints require API key in header:
```bash
X-API-Key: your-secret-api-key
```

## API Endpoints

### Grant Consent
```bash
POST /consent
```
Records user consent for a specific purpose.

**Request:**
```json
{
  "user_id": "user123",
  "purpose": "marketing",
  "metadata": "optional additional info"
}
```

**Response:**
```json
{
  "id": "consent-uuid",
  "user_id": "user123",
  "purpose": "marketing",
  "granted": true,
  "granted_at": "2026-03-08T10:30:00Z",
  "withdrawn_at": null
}
```

### Get User Consents
```bash
GET /consent/{user_id}?limit=100&offset=0
```
Retrieves all consents for a user (paginated, ordered by newest first).

**Query Parameters:**
- `limit` - Max records (default: 100, max: 1000)
- `offset` - Skip records (default: 0)

### Withdraw Consent
```bash
POST /consent/withdraw
```
Withdraws a specific consent.

**Request:**
```json
{
  "user_id": "user123",
  "consent_id": "consent-uuid"
}
```

**Response:**
```json
{
  "message": "Consent withdrawn successfully"
}
```

### Get Audit Logs
```bash
GET /audit/{user_id}?limit=100&offset=0
```
Retrieves audit trail for a user (paginated, ordered by newest first).

**Query Parameters:**
- `limit` - Max records (default: 100, max: 1000)
- `offset` - Skip records (default: 0)

## Example Usage

```bash
# Grant consent
curl -X POST "http://localhost:8000/consent" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "purpose": "marketing"}'

# Get user consents
curl -X GET "http://localhost:8000/consent/user123" \
  -H "X-API-Key: your-secret-api-key"

# Withdraw consent
curl -X POST "http://localhost:8000/consent/withdraw" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "consent_id": "consent-uuid"}'

# Get audit logs
curl -X GET "http://localhost:8000/audit/user123" \
  -H "X-API-Key: your-secret-api-key"
```

## Database Schema

### Consents Table
- `id` - Unique consent identifier (UUID)
- `user_id` - User identifier (indexed)
- `purpose` - Purpose of data processing
- `granted` - Consent status (boolean)
- `granted_at` - Timestamp when consent was granted
- `withdrawn_at` - Timestamp when consent was withdrawn (nullable)
- `metadata` - Additional information (optional)

### Audit Logs Table
- `id` - Unique log identifier (UUID)
- `user_id` - User identifier (indexed)
- `action` - Action performed (CONSENT_GRANTED, CONSENT_WITHDRAWN)
- `timestamp` - When action occurred
- `details` - Additional details about the action

## Configuration

### Environment Variables

- `API_KEY` - API key for authentication (required in production)
- `DATABASE_URL` - Database connection string (default: `sqlite:///dpdp_consent.db`)

### Database URLs

**SQLite (default):**
```bash
export DATABASE_URL="sqlite:///dpdp_consent.db"
```

**PostgreSQL:**
```bash
export DATABASE_URL="postgresql://user:password@localhost/dpdp_db"
```

**MySQL:**
```bash
export DATABASE_URL="mysql+pymysql://user:password@localhost/dpdp_db"
```

## DPDP Act 2023 Compliance

This platform implements core requirements of India's Digital Personal Data Protection Act:

- ✅ **Section 6** - Consent collection with clear purpose specification
- ✅ **Section 7** - Easy withdrawal mechanism
- ✅ **Section 8** - Audit trail for compliance verification
- ⚠️ **Partial** - Data retention policies (implement as needed)
- ⚠️ **Partial** - Right to data portability (add export endpoint)

## Production Deployment

1. **Set strong API key:**
   ```bash
   export API_KEY="$(openssl rand -hex 32)"
   ```

2. **Use production database:**
   ```bash
   export DATABASE_URL="postgresql://user:password@db-host/dpdp_db"
   ```

3. **Run with production server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

4. **Add HTTPS** - Use reverse proxy (nginx/traefik) with TLS

5. **Optional enhancements:**
   - Rate limiting (slowapi, fastapi-limiter)
   - Logging/monitoring (structlog, prometheus)
   - Consent expiry dates
   - Data export endpoint

## Security Notes

- Change default API key in production
- Use HTTPS in production
- Rotate API keys regularly
- Monitor audit logs for suspicious activity
- Consider adding rate limiting for public APIs

## License

MIT
