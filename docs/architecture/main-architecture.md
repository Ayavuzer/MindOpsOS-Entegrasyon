# MindOpsOS Entegrasyon - Multi-Tenant Architecture

**Versiyon:** 2.0  
**Tarih:** 2025-12-28  

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MindOpsOS Entegrasyon SaaS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐   │
│  │   Next.js Web     │    │   FastAPI         │    │   Background      │   │
│  │   (port 3002)     │───▶│   (port 8080)     │◀───│   Workers         │   │
│  │                   │    │                   │    │                   │   │
│  │  - Dashboard      │    │  - /api/auth      │    │  - Email Fetch    │   │
│  │  - Settings       │    │  - /api/emails    │    │  - PDF Parse      │   │
│  │  - Emails         │    │  - /api/tenant    │    │  - Sedna Sync     │   │
│  │  - Reservations   │    │  - /api/admin     │    │                   │   │
│  └───────────────────┘    └─────────┬─────────┘    └─────────┬─────────┘   │
│                                     │                        │             │
│                           ┌─────────▼────────────────────────▼─────────┐   │
│                           │              PostgreSQL 17                  │   │
│                           │  ┌────────────────────────────────────────┐│   │
│                           │  │ tenants    users    tenant_settings    ││   │
│                           │  │ emails     reservations  stop_sales    ││   │
│                           │  │ processing_logs                        ││   │
│                           │  └────────────────────────────────────────┘│   │
│                           └─────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

External Services:
┌─────────────────┐    ┌─────────────────┐
│  Mail Servers   │    │   Sedna API     │
│  (POP3/IMAP)    │    │   (per tenant)  │
└─────────────────┘    └─────────────────┘
```

---

## 2. Tech Stack

### Frontend

| Category | Technology | Version | Notes |
|----------|------------|---------|-------|
| Framework | Next.js | 16.x | App Router |
| Language | TypeScript | 5.x | Strict mode |
| Styling | Tailwind CSS | 4.x | Dark theme |
| Icons | Lucide React | Latest | Consistent icons |
| State | React hooks | Built-in | No Redux needed |
| Forms | React Hook Form | 7.x | Validation |
| HTTP | fetch | Built-in | Native API |

### Backend

| Category | Technology | Version | Notes |
|----------|------------|---------|-------|
| Framework | FastAPI | 0.115+ | Async |
| Language | Python | 3.11+ | Type hints |
| Database Driver | asyncpg | 0.29+ | Async PostgreSQL |
| Validation | Pydantic | 2.x | Request/Response models |
| Auth | python-jose | 3.x | JWT tokens |
| Encryption | cryptography | Latest | Fernet for secrets |
| Email | poplib, imaplib | Built-in | POP3/IMAP |
| HTTP Client | httpx | 0.27+ | Async Sedna calls |
| PDF | pymupdf | 1.23+ | PDF parsing |

### Infrastructure

| Category | Technology | Notes |
|----------|------------|-------|
| Database | PostgreSQL 17 | Docker: aria-postgres |
| Reverse Proxy | Nginx | Optional for prod |
| Container | Docker | Optional |
| Orchestration | K3s/K8s | Optional for scale |

---

## 3. Database Schema

### Core Tables

```sql
-- Tenant (Company/Agency)
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users (belong to tenant)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user', -- 'user', 'admin', 'superadmin'
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);

-- Tenant Settings (Integration Credentials)
CREATE TABLE tenant_settings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER UNIQUE NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Booking Email (POP3/IMAP)
    booking_email_host VARCHAR(255),
    booking_email_port INTEGER DEFAULT 995,
    booking_email_address VARCHAR(255),
    booking_email_password_encrypted BYTEA, -- Fernet encrypted
    booking_email_protocol VARCHAR(10) DEFAULT 'pop3', -- pop3, imap
    booking_email_use_ssl BOOLEAN DEFAULT TRUE,
    
    -- Stop Sale Email
    stopsale_email_host VARCHAR(255),
    stopsale_email_port INTEGER DEFAULT 995,
    stopsale_email_address VARCHAR(255),
    stopsale_email_password_encrypted BYTEA,
    stopsale_email_protocol VARCHAR(10) DEFAULT 'pop3',
    stopsale_email_use_ssl BOOLEAN DEFAULT TRUE,
    
    -- Sedna API
    sedna_api_url VARCHAR(500),
    sedna_username VARCHAR(255),
    sedna_password_encrypted BYTEA,
    sedna_operator_id INTEGER,
    
    -- Processing Settings
    email_check_interval_seconds INTEGER DEFAULT 60,
    auto_process_enabled BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sessions (JWT blacklist for logout)
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(255) UNIQUE NOT NULL, -- JWT ID
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_jti ON sessions(token_jti);
CREATE INDEX idx_sessions_user ON sessions(user_id);
```

### Existing Tables (Add tenant_id)

```sql
-- Add tenant_id to existing tables
ALTER TABLE emails ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE reservations ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE stop_sales ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
ALTER TABLE processing_logs ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);

-- Create indexes
CREATE INDEX idx_emails_tenant ON emails(tenant_id);
CREATE INDEX idx_reservations_tenant ON reservations(tenant_id);
CREATE INDEX idx_stop_sales_tenant ON stop_sales(tenant_id);
CREATE INDEX idx_processing_logs_tenant ON processing_logs(tenant_id);
```

---

## 4. API Design

### Authentication Endpoints

```yaml
POST /api/auth/register:
  request:
    email: string
    password: string
    company_name: string
  response:
    user: {id, email, tenant_id}
    token: string

POST /api/auth/login:
  request:
    email: string
    password: string
  response:
    user: {id, email, name, role, tenant_id}
    token: string
    expires_at: datetime

POST /api/auth/logout:
  headers:
    Authorization: Bearer <token>
  response:
    success: true

GET /api/auth/me:
  headers:
    Authorization: Bearer <token>
  response:
    user: {id, email, name, role, tenant}

POST /api/auth/forgot-password:
  request:
    email: string
  response:
    message: "Reset email sent"

POST /api/auth/reset-password:
  request:
    token: string
    new_password: string
  response:
    success: true
```

### Tenant Settings Endpoints

```yaml
GET /api/tenant/settings:
  headers:
    Authorization: Bearer <token>
  response:
    booking_email: {host, port, address, protocol, use_ssl}
    stopsale_email: {host, port, address, protocol, use_ssl}
    sedna: {api_url, username, operator_id}
    processing: {interval, auto_process}

PUT /api/tenant/settings:
  headers:
    Authorization: Bearer <token>
  request:
    booking_email: {host, port, address, password, ...}
    stopsale_email: {...}
    sedna: {api_url, username, password}
  response:
    success: true

POST /api/tenant/test/email:
  request:
    type: "booking" | "stopsale"
  response:
    success: boolean
    message: string
    details: {message_count?: number}

POST /api/tenant/test/sedna:
  response:
    success: boolean
    message: string
    details: {operator_id?: number}
```

### Protected Data Endpoints (tenant-scoped)

```yaml
# All existing endpoints now require auth and filter by tenant_id

GET /api/stats:
  # Returns stats for current tenant only

GET /api/emails:
  # Returns emails for current tenant only

GET /api/reservations:
  # Returns reservations for current tenant only

GET /api/stop-sales:
  # Returns stop sales for current tenant only
```

### Admin Endpoints (superadmin only)

```yaml
GET /api/admin/tenants:
  response:
    tenants: [{id, name, slug, is_active, user_count, email_count, created_at}]

GET /api/admin/tenants/{id}:
  response:
    tenant: {full details}
    stats: {emails, reservations, stop_sales}

PUT /api/admin/tenants/{id}/status:
  request:
    is_active: boolean
  response:
    success: true

GET /api/admin/system/health:
  response:
    database: {status, pool_size}
    workers: {active, queue_length}
    uptime: duration
```

---

## 5. Security Architecture

### Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  Login   │────▶│  Verify  │────▶│  Issue   │
│          │     │  Request │     │  Password│     │  JWT     │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
                                                        ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Access  │◀────│  Verify  │◀────│  Extract │◀────│  Bearer  │
│  Granted │     │  JWT     │     │  Token   │     │  Token   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### JWT Token Structure

```python
{
    "sub": "user_id",
    "tenant_id": 123,
    "email": "user@example.com",
    "role": "user",
    "exp": 1704067200,  # 1 hour
    "jti": "unique-token-id"
}
```

### Credential Encryption

```python
from cryptography.fernet import Fernet

# Master key from environment (ENCRYPTION_KEY)
fernet = Fernet(os.getenv("ENCRYPTION_KEY"))

def encrypt_credential(plain_text: str) -> bytes:
    return fernet.encrypt(plain_text.encode())

def decrypt_credential(encrypted: bytes) -> str:
    return fernet.decrypt(encrypted).decode()
```

### Tenant Isolation

```python
# Every DB query includes tenant_id
async def get_emails(tenant_id: int, ...):
    return await conn.fetch(
        "SELECT * FROM emails WHERE tenant_id = $1 ORDER BY ...",
        tenant_id
    )

# Dependency injection for tenant context
def get_current_tenant(token: str = Depends(oauth2_scheme)) -> TenantContext:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return TenantContext(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        role=payload["role"]
    )
```

---

## 6. Source Tree

```
MindOpsOS-Entegrasyon/
├── apps/
│   ├── api/                      # FastAPI Backend
│   │   ├── main.py               # Entry point
│   │   ├── auth/                 # NEW: Authentication
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py            # Token creation/verification
│   │   │   ├── password.py       # Hashing utilities
│   │   │   ├── dependencies.py   # get_current_user, get_current_tenant
│   │   │   └── routes.py         # /api/auth/* endpoints
│   │   ├── tenant/               # NEW: Tenant management
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # Pydantic models
│   │   │   ├── service.py        # Business logic
│   │   │   ├── encryption.py     # Credential encryption
│   │   │   └── routes.py         # /api/tenant/* endpoints
│   │   ├── admin/                # NEW: Admin panel
│   │   │   ├── __init__.py
│   │   │   └── routes.py         # /api/admin/* endpoints
│   │   └── routes/               # Existing routes (updated)
│   │       ├── stats.py
│   │       ├── emails.py
│   │       ├── reservations.py
│   │       └── stop_sales.py
│   │
│   └── web/                      # Next.js Frontend
│       ├── src/
│       │   ├── app/
│       │   │   ├── (auth)/       # NEW: Auth pages
│       │   │   │   ├── login/page.tsx
│       │   │   │   ├── register/page.tsx
│       │   │   │   └── forgot-password/page.tsx
│       │   │   ├── (dashboard)/   # Protected pages
│       │   │   │   ├── layout.tsx # Auth check + sidebar
│       │   │   │   ├── page.tsx   # Dashboard
│       │   │   │   ├── emails/
│       │   │   │   ├── reservations/
│       │   │   │   ├── stop-sales/
│       │   │   │   └── settings/  # NEW: Tenant settings
│       │   │   │       └── page.tsx
│       │   │   └── admin/         # NEW: Admin pages
│       │   │       ├── layout.tsx # Superadmin check
│       │   │       ├── tenants/
│       │   │       └── system/
│       │   ├── components/
│       │   │   ├── sidebar.tsx
│       │   │   ├── auth/          # NEW
│       │   │   │   ├── login-form.tsx
│       │   │   │   └── register-form.tsx
│       │   │   └── settings/      # NEW
│       │   │       ├── email-config.tsx
│       │   │       └── sedna-config.tsx
│       │   ├── lib/
│       │   │   ├── api.ts         # API client
│       │   │   └── auth.ts        # NEW: Auth context
│       │   └── hooks/
│       │       └── use-auth.ts    # NEW: Auth hook
│       └── .env.local
│
├── src/                          # Core services (existing)
│   ├── services/
│   │   ├── pop3_service.py       # Updated: tenant-aware
│   │   ├── sedna_client.py       # Updated: tenant credentials
│   │   └── ...
│   └── models/
│       ├── database.py           # Updated: tenant tables
│       └── ...
│
├── config/
│   └── .env                      # Add ENCRYPTION_KEY
│
├── docs/
│   ├── prd/
│   │   └── main-prd.md
│   └── architecture/
│       └── main-architecture.md   # This file
│
└── migrations/                    # NEW: DB migrations
    ├── 001_create_tenants.sql
    ├── 002_create_users.sql
    ├── 003_create_tenant_settings.sql
    └── 004_add_tenant_id_to_existing.sql
```

---

## 7. Coding Standards

### Python (Backend)

```python
# File naming: snake_case.py
# Class naming: PascalCase
# Function naming: snake_case
# Constants: UPPER_SNAKE_CASE

# Type hints required
async def get_user(user_id: int) -> User:
    ...

# Pydantic models for all requests/responses
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str

# Dependency injection for tenant context
@router.get("/emails")
async def list_emails(
    tenant: TenantContext = Depends(get_current_tenant),
    limit: int = Query(50, le=100)
):
    ...

# Error handling
class AppException(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})

# Logging
logger = structlog.get_logger(__name__)
logger.info("user_login", user_id=user.id, tenant_id=user.tenant_id)
```

### TypeScript (Frontend)

```typescript
// File naming: kebab-case.tsx
// Component naming: PascalCase
// Hook naming: useCamelCase
// Types: PascalCase with suffix

interface User {
  id: number;
  email: string;
  name: string;
  role: 'user' | 'admin' | 'superadmin';
  tenant: Tenant;
}

// API calls use centralized client
const api = {
  auth: {
    login: (data: LoginRequest) => fetch('/api/auth/login', {...}),
  },
  emails: {
    list: (params: EmailFilters) => fetch('/api/emails', {...}),
  },
};

// Auth context
const { user, login, logout, isLoading } = useAuth();

// Protected routes
export default function DashboardLayout({ children }) {
  const { user, isLoading } = useAuth();
  
  if (isLoading) return <LoadingSpinner />;
  if (!user) redirect('/login');
  
  return <>{children}</>;
}
```

---

## 8. Deployment Architecture

### Development (Local)

```yaml
# docker-compose.yml (optional)
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: aria
      POSTGRES_PASSWORD: aria_secure_2024
      POSTGRES_DB: mindops_entegrasyon
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: ./apps/api
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql://aria:aria_secure_2024@postgres:5432/mindops_entegrasyon
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      JWT_SECRET: ${JWT_SECRET}

  web:
    build: ./apps/web
    ports:
      - "3002:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8080
```

### Production (Kubernetes)

```yaml
# Namespace: mindops-entegrasyon
# Deployments: api, web, worker
# Services: api-svc, web-svc
# Ingress: entegrasyon.mindops.net
# Secrets: db-credentials, encryption-key, jwt-secret
```

---

## 9. Migration Strategy

### Phase 1: Schema Migration

1. Create new tables (tenants, users, tenant_settings)
2. Add tenant_id to existing tables
3. Create default tenant for existing data

### Phase 2: Code Migration

1. Add auth module
2. Update all endpoints with tenant filtering
3. Add tenant settings UI

### Phase 3: Data Migration

1. Move existing credentials to tenant_settings
2. Assign existing emails/reservations to default tenant

### Rollback Plan

- Keep v1.0 code in separate branch
- Database backups before each migration
- Feature flags for gradual rollout

---

## 10. Monitoring & Observability

### Metrics

- Active users per tenant
- Email processing rate
- Sedna sync success rate
- API response times

### Health Checks

- `/health` - Basic liveness
- `/health/ready` - Database + external services

### Logging

- Structured logs (JSON)
- Include tenant_id in all logs
- Log retention: 30 days

---

**Document Status:** Ready for Development  
**Next Step:** Start with E1-S1 (Database Schema)
