# Architecture: E13 - Advanced Email Integration

> **Epic:** E13
> **Versiyon:** 1.0
> **Tarih:** 2025-12-28

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MindOps Entegrasyon                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────┐    ┌─────────────────┐    ┌──────────────────┐ │
│  │  Next.js Web   │◄──►│   FastAPI API   │◄──►│   PostgreSQL     │ │
│  │    Frontend    │    │     Backend     │    │    (aria-postgres)│ │
│  └────────────────┘    └─────────────────┘    └──────────────────┘ │
│                               │                                      │
│                               ▼                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                  Email Integration Layer                       │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │  │ IMAP/IDLE   │  │ Gmail API   │  │ Microsoft Graph     │   │ │
│  │  │ Provider    │  │ Provider    │  │ Provider            │   │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │ │
│  │         │                │                     │               │ │
│  │         └────────────────┼─────────────────────┘               │ │
│  │                          ▼                                     │ │
│  │  ┌───────────────────────────────────────────────────────┐   │ │
│  │  │              EmailProviderInterface                    │   │ │
│  │  │  • fetch_unread_emails()                              │   │ │
│  │  │  • mark_as_read(uid)                                  │   │ │
│  │  │  • watch_inbox(callback)                              │   │ │
│  │  │  • get_connection_status()                            │   │ │
│  │  └───────────────────────────────────────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                  OAuth 2.0 Integration                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │
│  │  │ Google      │  │ Microsoft   │  │ Token Manager       │   │ │
│  │  │ OAuth       │  │ OAuth       │  │ (Refresh, Store)    │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │        External Services       │
              ├────────────────────────────────┤
              │  • Gmail (IMAP / API)          │
              │  • Outlook (IMAP / Graph API)  │
              │  • Generic IMAP servers        │
              │  • Google OAuth                │
              │  • Microsoft Entra ID          │
              └────────────────────────────────┘
```

---

## 2. Tech Stack

### 2.1 Backend (Existing + New)

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Framework | FastAPI | 0.104+ | Async support |
| Database | PostgreSQL | 17 | Via aria-postgres |
| ORM | asyncpg | 0.29+ | Raw SQL preferred |
| Email (IMAP) | imaplib | stdlib | Python standard |
| Email (IMAP Async) | aioimaplib | 1.0+ | **NEW** - Async IMAP |
| Gmail API | google-api-python-client | 2.x | **NEW** |
| MS Graph | msgraph-sdk | 1.x | **NEW** |
| OAuth | authlib | 1.3+ | **NEW** - OAuth flows |
| Encryption | cryptography (Fernet) | 42.x | Existing |
| Background Tasks | asyncio | stdlib | Task scheduling |

### 2.2 Frontend (Existing + New)

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Framework | Next.js | 14 | App Router |
| UI Components | shadcn/ui | latest | Existing |
| Forms | react-hook-form | 7.x | Existing |
| OAuth Popup | Custom | - | **NEW** - OAuth flow |

---

## 3. Data Models

### 3.1 Database Schema Changes

```sql
-- Migration: 20251229_oauth_support.sql

-- Add OAuth columns to tenant_settings
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_provider VARCHAR(50);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_client_id VARCHAR(255);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_client_secret_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_access_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_refresh_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_token_expiry TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_oauth_scopes TEXT[];

ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_provider VARCHAR(50);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_client_id VARCHAR(255);
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_client_secret_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_access_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_refresh_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_token_expiry TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_oauth_scopes TEXT[];

-- Add email health tracking
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_last_success_at TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_last_error TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_email_error_count_24h INTEGER DEFAULT 0;

ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_last_success_at TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_last_error TEXT;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_email_error_count_24h INTEGER DEFAULT 0;

-- Add real-time settings
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS booking_use_idle BOOLEAN DEFAULT TRUE;
ALTER TABLE tenant_settings ADD COLUMN IF NOT EXISTS stopsale_use_idle BOOLEAN DEFAULT TRUE;

-- Indexes for health queries
CREATE INDEX IF NOT EXISTS idx_tenant_settings_email_health 
    ON tenant_settings(booking_email_last_success_at, stopsale_email_last_success_at);
```

### 3.2 Pydantic Models

```python
# apps/api/email/models.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    NONE = "none"


class OAuthConfig(BaseModel):
    """OAuth 2.0 configuration."""
    
    provider: OAuthProvider = OAuthProvider.NONE
    client_id: Optional[str] = None
    # Note: client_secret never returned to frontend
    access_token: Optional[str] = None  # Never returned
    refresh_token: Optional[str] = None  # Never returned
    token_expiry: Optional[datetime] = None
    scopes: list[str] = []
    
    # Display info (safe to return)
    connected_email: Optional[str] = None
    is_connected: bool = False


class EmailAuthMethod(str, Enum):
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    APP_PASSWORD = "app_password"


class EnhancedEmailConfig(BaseModel):
    """Enhanced email configuration with OAuth support."""
    
    # Server settings
    host: Optional[str] = None
    port: int = 993
    address: Optional[str] = None
    protocol: str = "imap"  # imap, pop3
    use_ssl: bool = True
    
    # Authentication
    auth_method: EmailAuthMethod = EmailAuthMethod.PASSWORD
    password: Optional[str] = None  # Only for input
    oauth: Optional[OAuthConfig] = None
    
    # Real-time settings
    use_idle: bool = True
    folder: str = "INBOX"
    
    # Health info (read-only)
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count_24h: int = 0


class EmailHealthStatus(BaseModel):
    """Email connection health status."""
    
    tenant_id: int
    email_type: str  # booking, stopsale
    
    connection_status: str  # connected, disconnected, error
    last_connection_at: Optional[datetime]
    last_error: Optional[str]
    error_count_24h: int
    
    emails_processed_24h: int
    emails_failed_24h: int
    average_processing_time_ms: float


class OAuthAuthorizeResponse(BaseModel):
    """OAuth authorization URL response."""
    
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    
    code: str
    state: str
```

---

## 4. API Endpoints

### 4.1 OAuth Endpoints

```yaml
# OAuth Flow Endpoints

POST /api/oauth/{provider}/authorize
  description: Get OAuth authorization URL
  params:
    provider: google | microsoft
    email_type: booking | stopsale
  response:
    authorization_url: string
    state: string

GET /api/oauth/{provider}/callback
  description: OAuth callback handler
  params:
    code: string
    state: string
  response:
    success: boolean
    message: string
    connected_email: string

DELETE /api/oauth/{provider}/disconnect
  description: Disconnect OAuth
  params:
    email_type: booking | stopsale
  response:
    success: boolean
```

### 4.2 Health Endpoints

```yaml
# Health Monitoring Endpoints

GET /api/tenant/email/health
  description: Get email connection health
  response:
    booking:
      status: connected | disconnected | error
      last_sync: datetime
      error_count: int
    stopsale:
      status: connected | disconnected | error
      last_sync: datetime
      error_count: int

GET /api/tenant/email/stats
  description: Get email processing statistics
  response:
    processed_24h: int
    failed_24h: int
    avg_processing_time_ms: float
    queue_size: int
```

---

## 5. Component Architecture

### 5.1 Email Provider Interface

```python
# apps/api/email/providers/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Awaitable


class EmailProviderInterface(ABC):
    """Abstract interface for email providers."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass
    
    @abstractmethod
    async def fetch_unread_emails(
        self, 
        max_count: int = 50
    ) -> AsyncIterator['EmailMessage']:
        """Fetch unread emails."""
        pass
    
    @abstractmethod
    async def mark_as_read(self, email_id: str) -> bool:
        """Mark email as read."""
        pass
    
    @abstractmethod
    async def watch_inbox(
        self,
        on_new_email: Callable[['EmailMessage'], Awaitable[None]]
    ) -> None:
        """Watch inbox for new emails (IDLE/Push)."""
        pass
    
    @abstractmethod
    async def get_health_status(self) -> dict:
        """Get connection health status."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
```

### 5.2 Provider Implementations

```
apps/api/email/providers/
├── __init__.py
├── base.py                 # EmailProviderInterface
├── imap_provider.py        # IMAP/IDLE implementation
├── gmail_provider.py       # Gmail API implementation
├── graph_provider.py       # Microsoft Graph implementation
└── factory.py              # Provider factory
```

### 5.3 OAuth Service

```python
# apps/api/oauth/service.py

class OAuthService:
    """OAuth 2.0 service for email providers."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.google_config = GoogleOAuthConfig()
        self.microsoft_config = MicrosoftOAuthConfig()
    
    async def get_authorization_url(
        self,
        provider: str,
        tenant_id: int,
        email_type: str,
    ) -> OAuthAuthorizeResponse:
        """Generate OAuth authorization URL."""
        pass
    
    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> dict:
        """Handle OAuth callback and store tokens."""
        pass
    
    async def refresh_token_if_needed(
        self,
        tenant_id: int,
        email_type: str,
    ) -> bool:
        """Refresh token if about to expire."""
        pass
    
    async def disconnect(
        self,
        tenant_id: int,
        email_type: str,
    ) -> bool:
        """Remove OAuth connection."""
        pass
```

### 5.4 Email Orchestrator

```python
# apps/api/email/orchestrator.py

class TenantEmailOrchestrator:
    """Orchestrates email watching for all tenants."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.watchers: dict[str, EmailProviderInterface] = {}
        self.running = False
    
    async def start(self) -> None:
        """Start watching for all active tenants."""
        self.running = True
        
        # Load all tenant configurations
        async with self.db_pool.acquire() as conn:
            tenants = await conn.fetch("""
                SELECT t.id, ts.*
                FROM tenants t
                JOIN tenant_settings ts ON t.id = ts.tenant_id
                WHERE t.is_active = true
            """)
        
        # Start watcher for each tenant
        for tenant in tenants:
            await self._start_tenant_watcher(tenant)
    
    async def stop(self) -> None:
        """Stop all watchers."""
        self.running = False
        for key, watcher in self.watchers.items():
            await watcher.disconnect()
        self.watchers.clear()
    
    async def add_tenant(self, tenant_id: int) -> None:
        """Add watcher for new tenant."""
        pass
    
    async def remove_tenant(self, tenant_id: int) -> None:
        """Remove watcher for tenant."""
        pass
    
    async def refresh_tenant(self, tenant_id: int) -> None:
        """Refresh watcher after settings change."""
        pass
```

---

## 6. Source Tree (New Files)

```
apps/api/
├── email/
│   ├── __init__.py
│   ├── models.py                    # New Pydantic models
│   ├── orchestrator.py              # NEW: Tenant orchestrator
│   ├── connection_pool.py           # NEW: Connection pooling
│   └── providers/
│       ├── __init__.py
│       ├── base.py                  # NEW: Provider interface
│       ├── imap_provider.py         # NEW: IMAP/IDLE provider
│       ├── gmail_provider.py        # NEW: Gmail API provider
│       ├── graph_provider.py        # NEW: MS Graph provider
│       └── factory.py               # NEW: Provider factory
│
├── oauth/
│   ├── __init__.py
│   ├── routes.py                    # NEW: OAuth endpoints
│   ├── service.py                   # NEW: OAuth service
│   ├── google.py                    # NEW: Google OAuth
│   ├── microsoft.py                 # NEW: Microsoft OAuth
│   └── token_manager.py             # NEW: Token refresh

apps/web/src/
├── app/
│   └── settings/
│       └── email/
│           ├── page.tsx             # MODIFIED: OAuth UI
│           └── components/
│               ├── OAuthConnect.tsx     # NEW
│               ├── ConnectionHealth.tsx # NEW
│               └── ProviderSelect.tsx   # NEW
```

---

## 7. Security Considerations

### 7.1 Token Storage

```python
# All OAuth tokens encrypted with Fernet
ENCRYPTED_FIELDS = [
    "oauth_client_secret_encrypted",
    "oauth_access_token_encrypted", 
    "oauth_refresh_token_encrypted",
]

# Never return to frontend
NEVER_EXPOSE = [
    "access_token",
    "refresh_token",
    "client_secret",
]
```

### 7.2 OAuth State Parameter

```python
# CSRF protection via state parameter
def generate_state(tenant_id: int, email_type: str) -> str:
    payload = {
        "tenant_id": tenant_id,
        "email_type": email_type,
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.utcnow() + timedelta(minutes=10)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

### 7.3 Scope Minimization

```python
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

MICROSOFT_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "offline_access",  # For refresh token
]
```

---

## 8. Error Handling

### 8.1 Retry Strategy

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
)
async def fetch_with_retry():
    pass
```

### 8.2 Health Monitoring

```python
class EmailHealthMonitor:
    """Monitor email connection health."""
    
    async def record_success(self, tenant_id: int, email_type: str):
        await self.db.execute("""
            UPDATE tenant_settings
            SET {email_type}_email_last_success_at = NOW(),
                {email_type}_email_error_count_24h = 0
            WHERE tenant_id = $1
        """, tenant_id)
    
    async def record_error(self, tenant_id: int, email_type: str, error: str):
        await self.db.execute("""
            UPDATE tenant_settings
            SET {email_type}_email_last_error = $2,
                {email_type}_email_error_count_24h = 
                    {email_type}_email_error_count_24h + 1
            WHERE tenant_id = $1
        """, tenant_id, error)
```

---

## 9. Environment Variables

```bash
# OAuth - Google
GOOGLE_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=xxx
GOOGLE_OAUTH_REDIRECT_URI=https://entegrasyon.mindops.net/api/oauth/google/callback

# OAuth - Microsoft
MICROSOFT_OAUTH_CLIENT_ID=xxx
MICROSOFT_OAUTH_CLIENT_SECRET=xxx
MICROSOFT_OAUTH_TENANT_ID=common  # or specific tenant
MICROSOFT_OAUTH_REDIRECT_URI=https://entegrasyon.mindops.net/api/oauth/microsoft/callback

# Email Processing
EMAIL_IDLE_TIMEOUT_SECONDS=1740  # 29 minutes
EMAIL_CONNECTION_POOL_SIZE=5
EMAIL_RETRY_MAX_ATTEMPTS=3
```

---

## 10. Deployment Considerations

### 10.1 Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oauth-secrets
  namespace: entegrasyon
type: Opaque
stringData:
  GOOGLE_OAUTH_CLIENT_ID: "xxx"
  GOOGLE_OAUTH_CLIENT_SECRET: "xxx"
  MICROSOFT_OAUTH_CLIENT_ID: "xxx"
  MICROSOFT_OAUTH_CLIENT_SECRET: "xxx"
```

### 10.2 Health Probes

```yaml
# Update deployment with email health check
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30

# Add email orchestrator startup
lifecycle:
  postStart:
    exec:
      command: ["/bin/sh", "-c", "curl -X POST localhost:8080/api/internal/start-watchers"]
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/email/test_providers.py

class TestImapProvider:
    async def test_connect_success(self, mock_imap):
        pass
    
    async def test_fetch_unread_emails(self, mock_imap):
        pass
    
    async def test_idle_watch(self, mock_imap):
        pass

class TestOAuthService:
    async def test_generate_google_auth_url(self):
        pass
    
    async def test_handle_callback(self, mock_google_client):
        pass
    
    async def test_refresh_token(self):
        pass
```

### 11.2 Integration Tests

```python
# tests/integration/test_oauth_flow.py

class TestGoogleOAuthFlow:
    async def test_full_flow(self, test_client, mock_google):
        # 1. Get authorization URL
        # 2. Simulate callback
        # 3. Verify token storage
        # 4. Verify email fetch
        pass
```

---

*Architecture document for E13 - Advanced Email Integration*
