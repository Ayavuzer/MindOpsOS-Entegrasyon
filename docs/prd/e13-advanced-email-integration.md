# PRD: E13 - Advanced Email Integration (AEI)

> **Proje:** MindOps Entegrasyon
> **Epic:** E13
> **Versiyon:** 1.0
> **Tarih:** 2025-12-28
> **Yazar:** BMad PM + Dr. Elena Vasquez (Research)

---

## 1. Özet ve Hedefler

### 1.1 Problem Statement

Mevcut email entegrasyonu temel IMAP/POP3 desteği sunmaktadır ancak:

- **Güvenlik:** Password-based authentication artık Google ve Microsoft tarafından desteklenmiyor
- **Performans:** Polling tabanlı sistem gereksiz yük oluşturuyor ve gecikmelere neden oluyor
- **Ölçeklenebilirlik:** Her tenant için connection pooling yok
- **Güvenilirlik:** Retry logic ve health monitoring eksik

### 1.2 Goals

| Goal | Metric | Target |
|------|--------|--------|
| Modern Auth | OAuth 2.0 adoption | 100% of new tenants |
| Real-time | Email processing latency | < 5 seconds |
| Reliability | Uptime | 99.5% |
| Efficiency | Server load reduction | 90% reduction via IDLE |

### 1.3 Success Criteria

- [ ] OAuth 2.0 ile Gmail ve Outlook bağlantısı kurulabilmeli
- [ ] IMAP IDLE ile real-time email bildirimi alınabilmeli
- [ ] Settings sayfasında OAuth flow tamamlanabilmeli
- [ ] Connection health dashboard'da görüntülenebilmeli

---

## 2. Kullanıcı Hikayeleri

### Persona: Acente Yöneticisi (Ahmet)

> "Gmail hesabımı bağlamak istiyordum ama şifre ile bağlanamıyorum.
> Google artık less secure apps'i desteklemiyor diyorlar."

### Persona: IT Admin (Zeynep)

> "Her tenant için email bağlantısının sağlıklı çalışıp çalışmadığını
> kontrol etmek istiyorum. Hata durumunda anında müdahale edebilmeliyim."

---

## 3. Gereksinimler

### 3.1 Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-01 | OAuth 2.0 authentication for Gmail | P1 | Google OAuth flow |
| FR-02 | OAuth 2.0 authentication for Outlook | P1 | Microsoft Graph OAuth |
| FR-03 | Token auto-refresh mechanism | P1 | Before expiry |
| FR-04 | IMAP IDLE real-time watching | P1 | Push notifications |
| FR-05 | Connection pool management | P1 | Max 5 per tenant |
| FR-06 | Retry logic with exponential backoff | P1 | Max 3 attempts |
| FR-07 | Settings UI OAuth flow | P1 | Connect button |
| FR-08 | Connection health status display | P2 | Dashboard widget |
| FR-09 | Gmail API native integration | P2 | Optional, for push |
| FR-10 | Microsoft Graph API integration | P2 | Optional, for push |
| FR-11 | Email processing queue | P2 | For high volume |
| FR-12 | Multi-folder monitoring | P3 | Beyond INBOX |

### 3.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Response time | < 500ms for OAuth callback |
| NFR-02 | Concurrent connections | Support 100 tenants |
| NFR-03 | Token storage | Encrypted with Fernet |
| NFR-04 | Backward compatibility | Existing password auth continues |
| NFR-05 | Documentation | OpenAPI + setup guide |

---

## 4. Technical Constraints

### 4.1 Existing System

- **Backend:** FastAPI + asyncpg
- **Frontend:** Next.js 14
- **Database:** PostgreSQL (aria-postgres)
- **Auth:** JWT tokens with Fernet encryption

### 4.2 External Dependencies

| Service | Requirement | Notes |
|---------|-------------|-------|
| Google Cloud | OAuth 2.0 credentials | Project in Cloud Console |
| Microsoft Azure | App registration | Entra ID |
| SMTP/IMAP | Standard protocol support | Port 993 (IMAPS) |

### 4.3 Constraints

- OAuth callback URL must be HTTPS
- Token refresh must happen before expiry
- IMAP IDLE timeout is 29 minutes (Gmail limit)

---

## 5. Epic & Story Breakdown

### Epic E13: Advanced Email Integration

**Total Effort:** 63 Story Points  
**Duration:** 8 Sprints (4 Phases)

---

### Phase 1: Foundation (Sprint 1-2) - 24 SP

#### E13-S1: OAuth 2.0 Data Model (5 SP)

**As a** developer  
**I want** OAuth credentials stored securely  
**So that** tokens can be managed per tenant

**Acceptance Criteria:**

- [ ] Database migration with new columns
- [ ] OAuth config model in Pydantic
- [ ] Encryption for client_secret and tokens
- [ ] Unit tests for model

**Technical Notes:**

```sql
ALTER TABLE tenant_settings ADD COLUMN oauth_provider VARCHAR(50);
ALTER TABLE tenant_settings ADD COLUMN oauth_client_id VARCHAR(255);
ALTER TABLE tenant_settings ADD COLUMN oauth_client_secret_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN oauth_access_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN oauth_refresh_token_encrypted TEXT;
ALTER TABLE tenant_settings ADD COLUMN oauth_token_expiry TIMESTAMPTZ;
ALTER TABLE tenant_settings ADD COLUMN oauth_scopes TEXT[];
```

---

#### E13-S2: Google OAuth Flow - Backend (8 SP)

**As a** tenant admin  
**I want** to connect Gmail via OAuth  
**So that** I don't need to use app passwords

**Acceptance Criteria:**

- [ ] `/api/oauth/google/authorize` endpoint
- [ ] `/api/oauth/google/callback` endpoint
- [ ] Token storage after successful auth
- [ ] Error handling for denied access
- [ ] Integration test with mock

**Technical Notes:**

- Scopes: `https://mail.google.com/`
- PKCE flow for security
- State parameter for CSRF protection

---

#### E13-S3: Google OAuth Flow - Frontend (5 SP)

**As a** tenant admin  
**I want** a "Connect with Google" button  
**So that** I can easily link my account

**Acceptance Criteria:**

- [ ] OAuth connect button in Settings
- [ ] Popup/redirect flow handling
- [ ] Success/error feedback
- [ ] Connected status display
- [ ] Disconnect option

---

#### E13-S4: Token Refresh Mechanism (3 SP)

**As a** system  
**I want** tokens refreshed automatically  
**So that** connections don't expire

**Acceptance Criteria:**

- [ ] Background task for token refresh
- [ ] Refresh 5 minutes before expiry
- [ ] Handle refresh failures gracefully
- [ ] Fallback to re-authentication prompt

---

#### E13-S5: Microsoft OAuth Flow (3 SP)

**As a** tenant admin  
**I want** to connect Outlook/Office 365  
**So that** I can use my work email

**Acceptance Criteria:**

- [ ] Azure AD app registration docs
- [ ] `/api/oauth/microsoft/authorize` endpoint
- [ ] `/api/oauth/microsoft/callback` endpoint
- [ ] Multi-tenant support

---

### Phase 2: Real-time (Sprint 3-4) - 16 SP

#### E13-S6: IMAP IDLE Implementation (8 SP)

**As a** system  
**I want** real-time email notifications  
**So that** bookings are processed instantly

**Acceptance Criteria:**

- [ ] EmailIdleWatcher class
- [ ] 29-minute timeout handling
- [ ] Reconnection on disconnect
- [ ] Per-tenant watching
- [ ] Graceful shutdown

**Technical Notes:**

```python
class EmailIdleWatcher:
    async def watch_inbox(self, on_new_email: Callable)
    async def stop(self)
```

---

#### E13-S7: Connection Pool & Retry (5 SP)

**As a** developer  
**I want** connection pooling  
**So that** resources are managed efficiently

**Acceptance Criteria:**

- [ ] EmailConnectionPool class
- [ ] Max 5 connections per tenant
- [ ] Exponential backoff retry
- [ ] Connection health check
- [ ] Pool statistics endpoint

---

#### E13-S8: Health Monitoring (3 SP)

**As an** IT admin  
**I want** to see connection health  
**So that** I can troubleshoot issues

**Acceptance Criteria:**

- [ ] `/api/tenant/email/health` endpoint
- [ ] Last successful connection timestamp
- [ ] Error count in last 24h
- [ ] Processing statistics

---

### Phase 3: Native APIs (Sprint 5-6) - 18 SP

#### E13-S9: Gmail API Service (8 SP)

**As a** developer  
**I want** native Gmail integration  
**So that** we can use push notifications

**Acceptance Criteria:**

- [ ] GmailService class
- [ ] Fetch unread emails via API
- [ ] Mark as read via API
- [ ] Attachment download
- [ ] Label management

---

#### E13-S10: Microsoft Graph Service (8 SP)

**As a** developer  
**I want** native Graph integration  
**So that** Office 365 users get best experience

**Acceptance Criteria:**

- [ ] MicrosoftGraphEmailService class
- [ ] Fetch messages endpoint
- [ ] Delta query for changes
- [ ] Webhook subscription (optional)

---

#### E13-S11: Provider Abstraction Layer (2 SP)

**As a** developer  
**I want** unified email interface  
**So that** provider logic is encapsulated

**Acceptance Criteria:**

- [ ] EmailProviderInterface abstract class
- [ ] ImapProvider implementation
- [ ] GmailProvider implementation
- [ ] GraphProvider implementation

---

### Phase 4: Enterprise (Sprint 7-8) - 5 SP

#### E13-S12: Multi-Tenant Orchestration (3 SP)

**As a** system  
**I want** orchestrated email watching  
**So that** all tenants are monitored

**Acceptance Criteria:**

- [ ] TenantEmailOrchestrator service
- [ ] Startup initialization
- [ ] Dynamic tenant add/remove
- [ ] Resource limits per tenant

---

#### E13-S13: Email Dashboard Widget (2 SP)

**As a** tenant admin  
**I want** email stats on dashboard  
**So that** I see processing activity

**Acceptance Criteria:**

- [ ] EmailStatsWidget component
- [ ] Emails processed today
- [ ] Success/failure rates
- [ ] Last sync timestamp

---

## 6. UI/UX Considerations

### 6.1 Settings Page Updates

```
┌─────────────────────────────────────────────────────────────┐
│  📧 Email Configuration                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Authentication Method:                                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ◉ OAuth 2.0 (Recommended)                               ││
│  │ ○ Password (Legacy - disabled for Gmail/Outlook)        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Selected Provider:                                          │
│  [ Gmail ▾ ]  [ Outlook/Office 365 ]  [ Other IMAP ]        │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ 🔗 Connect with Google                                   ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  ✅ Connected as: booking@demo-agency.com                    │
│  Token expires: 2025-01-28 15:30 (auto-refresh enabled)     │
│                                                              │
│  ☑ Enable Real-time Notifications (IMAP IDLE)               │
│  ☐ Use Gmail API for Push (requires Pub/Sub setup)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Health Status Widget

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Email Connection Health                                  │
├─────────────────────────────────────────────────────────────┤
│  Booking Email        │ 🟢 Connected │ Last: 2 min ago      │
│  Stop-Sale Email      │ 🟢 Connected │ Last: 5 min ago      │
│                                                              │
│  Today: 47 processed │ 2 failed │ Avg: 1.2s                │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Rollout Plan

### Phase 1: Internal Testing

- OAuth flow with test accounts
- IMAP IDLE stability testing
- 72-hour stability test

### Phase 2: Beta Rollout

- Select 3-5 tenants
- Parallel password + OAuth
- Collect feedback

### Phase 3: General Availability

- Enable for all new tenants
- Migration guide for existing
- Deprecation notice for password auth

---

## 8. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| OAuth token revocation | High | Low | Graceful re-auth prompt |
| IMAP IDLE disconnect | Medium | Medium | Auto-reconnect, fallback polling |
| Google/MS API limits | High | Low | Rate limiting, quota monitoring |
| Credential migration | Medium | Medium | Parallel support period |

---

## 9. References

- [Research Report](/.agent/artifacts/research/2025-12-28-mail-settings-improvement-analysis.md)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Microsoft Graph API](https://docs.microsoft.com/graph/api/resources/mail-api-overview)
- [IMAP IDLE RFC 2177](https://tools.ietf.org/html/rfc2177)

---

## 10. Appendix: Story Status Tracker

| Story ID | Title | SP | Status | Sprint |
|----------|-------|---:|--------|--------|
| E13-S1 | OAuth Data Model | 5 | 📋 Backlog | 1 |
| E13-S2 | Google OAuth Backend | 8 | 📋 Backlog | 1 |
| E13-S3 | Google OAuth Frontend | 5 | 📋 Backlog | 2 |
| E13-S4 | Token Refresh | 3 | 📋 Backlog | 2 |
| E13-S5 | Microsoft OAuth | 3 | 📋 Backlog | 2 |
| E13-S6 | IMAP IDLE | 8 | 📋 Backlog | 3 |
| E13-S7 | Connection Pool | 5 | 📋 Backlog | 3 |
| E13-S8 | Health Monitoring | 3 | 📋 Backlog | 4 |
| E13-S9 | Gmail API | 8 | 📋 Backlog | 5 |
| E13-S10 | MS Graph API | 8 | 📋 Backlog | 5 |
| E13-S11 | Provider Abstraction | 2 | 📋 Backlog | 6 |
| E13-S12 | Orchestration | 3 | 📋 Backlog | 7 |
| E13-S13 | Dashboard Widget | 2 | 📋 Backlog | 8 |

**Total: 63 SP**

---

*Document created by BMad PM Agent + Research by Dr. Elena Vasquez*
