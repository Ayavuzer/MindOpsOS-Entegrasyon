# MindOpsOS Entegrasyon - Multi-Tenant SaaS PRD

**Versiyon:** 2.0  
**Tarih:** 2025-12-28  
**Yazar:** Ali Yavuzer  
**Durum:** Draft

---

## 1. Executive Summary

### Problem

Point Holiday şu anda Juniper Travel Technology'den gelen rezervasyon email'lerini manuel olarak Sedna Agency sistemine girmektedir. Mevcut MindOpsOS-Entegrasyon v1.0 bu sorunu tek bir kullanıcı (Point Holiday) için çözmektedir. Ancak aynı çözüme ihtiyaç duyan onlarca tur operatörü ve seyahat acentesi bulunmaktadır.

### Çözüm

Mevcut sistemi multi-tenant SaaS platformuna dönüştürerek:

- Her acente kendi email ve Sedna API ayarlarını yapabilir
- Her acente kendi dashboard'unda verilerini görebilir
- Merkezi yönetim paneli ile tüm tenant'lar izlenebilir

### Hedef Kitle

- Tur operatörleri
- Seyahat acenteleri
- Otel satış temsilcileri
- B2B turizm işletmeleri

### Başarı Metrikleri

| Metrik | Hedef | Ölçüm |
|--------|-------|-------|
| Kayıtlı Tenant Sayısı | 10+ (6 ay) | User signups |
| Aktif Kullanıcı | %70 haftalık | Login frequency |
| Email İşleme Doğruluğu | %99+ | Success rate |
| Sistem Uptime | %99.9 | Monitoring |

---

## 2. Kullanıcı Personaları

### Persona 1: Acente Sahibi (Owner)

**Adı:** Mehmet Demir  
**Rol:** Seyahat Acentesi Sahibi  
**Teknik Yeterlilik:** Orta  

**İhtiyaçlar:**

- Sistemin kendisi için çalışmasını istiyor
- Teknik detaylarla uğraşmak istemiyor
- Dashboard'dan günlük özet görmek istiyor

**Acıları:**

- Manuel email okuma ve Sedna'ya giriş (günde 30+ dakika)
- Rezervasyon kaçırma riski
- Stop sale güncelleme gecikmeleri

### Persona 2: Operasyon Personeli

**Adı:** Ayşe Yılmaz  
**Rol:** Rezervasyon Uzmanı  
**Teknik Yeterlilik:** Düşük  

**İhtiyaçlar:**

- Sadece işlenmiş verileri görmek
- Hata durumunda manuel müdahale
- Basit, anlaşılır arayüz

### Persona 3: Sistem Admini

**Adı:** Platform Operatörü  
**Rol:** SaaS Yöneticisi  
**Teknik Yeterlilik:** Yüksek  

**İhtiyaçlar:**

- Tüm tenant'ları izleme
- Sistem sağlığı monitoring
- Tenant yönetimi (suspension, limits)

---

## 3. Fonksiyonel Gereksinimler (FR)

### FR-1: User Management (Kullanıcı Yönetimi)

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-1.1 | Email + şifre ile kayıt | P0 |
| FR-1.2 | Email doğrulama | P1 |
| FR-1.3 | Giriş / Çıkış | P0 |
| FR-1.4 | Şifre sıfırlama | P1 |
| FR-1.5 | Profil düzenleme | P2 |
| FR-1.6 | OAuth (Google) | P3 |

### FR-2: Tenant Settings (Entegrasyon Ayarları)

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-2.1 | Booking Email ayarları (POP3/IMAP) | P0 |
| FR-2.2 | Stop Sale Email ayarları | P0 |
| FR-2.3 | Sedna API credentials | P0 |
| FR-2.4 | Connection test (email) | P0 |
| FR-2.5 | Connection test (Sedna) | P0 |
| FR-2.6 | Ayarları şifreli saklama | P0 |
| FR-2.7 | Mapping konfigürasyonu (hotel, room) | P2 |

### FR-3: Dashboard

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-3.1 | Email istatistikleri (bugün, toplam) | P0 |
| FR-3.2 | Processing status (pending, processed, failed) | P0 |
| FR-3.3 | Rezervasyon sayısı | P0 |
| FR-3.4 | Stop sale sayısı | P0 |
| FR-3.5 | Success rate | P1 |
| FR-3.6 | Quick actions | P1 |

### FR-4: Email Management

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-4.1 | Email listesi görüntüleme | P0 |
| FR-4.2 | Email detayı görüntüleme | P0 |
| FR-4.3 | Status/type filtrele | P1 |
| FR-4.4 | Manual reprocess | P1 |
| FR-4.5 | PDF attachment indirme | P2 |

### FR-5: Reservation Management

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-5.1 | Rezervasyon listesi | P0 |
| FR-5.2 | Sedna sync durumu | P0 |
| FR-5.3 | Manual Sedna sync | P1 |
| FR-5.4 | Rezervasyon detayı | P1 |

### FR-6: Stop Sale Management

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-6.1 | Stop sale listesi | P0 |
| FR-6.2 | Date range filtresi | P1 |
| FR-6.3 | Hotel filtresi | P1 |

### FR-7: Admin Panel (Superadmin)

| ID | Gereksinim | Öncelik |
|----|------------|---------|
| FR-7.1 | Tüm tenant listesi | P1 |
| FR-7.2 | Tenant istatistikleri | P1 |
| FR-7.3 | Tenant suspend/activate | P2 |
| FR-7.4 | System health dashboard | P2 |

---

## 4. Non-Fonksiyonel Gereksinimler (NFR)

### NFR-1: Security

| ID | Gereksinim | Hedef |
|----|------------|-------|
| NFR-1.1 | Password hashing | bcrypt/argon2 |
| NFR-1.2 | API credentials encryption | AES-256 |
| NFR-1.3 | Tenant data isolation | %100 |
| NFR-1.4 | Rate limiting | 100 req/min |
| NFR-1.5 | HTTPS only | TLS 1.3 |
| NFR-1.6 | Session management | JWT (1h expire) |

### NFR-2: Performance

| ID | Gereksinim | Hedef |
|----|------------|-------|
| NFR-2.1 | Page load time | < 2s |
| NFR-2.2 | API response time | < 200ms (P95) |
| NFR-2.3 | Email processing | < 5s per email |
| NFR-2.4 | Concurrent users | 100+ |

### NFR-3: Scalability

| ID | Gereksinim | Hedef |
|----|------------|-------|
| NFR-3.1 | Tenant count | 1000+ |
| NFR-3.2 | Emails per tenant/day | 1000+ |
| NFR-3.3 | Data retention | 1 year |

### NFR-4: Availability

| ID | Gereksinim | Hedef |
|----|------------|-------|
| NFR-4.1 | Uptime | 99.9% |
| NFR-4.2 | Scheduled maintenance | < 4h/month |
| NFR-4.3 | Data backup | Daily |

---

## 5. Technical Assumptions

### Tech Stack

| Layer | Technology | Reason |
|-------|------------|--------|
| Frontend | Next.js 16, React 19, TypeScript | Existing, modern |
| UI Components | Tailwind CSS, Lucide Icons | Existing |
| Backend API | FastAPI, Python 3.11 | Existing |
| Database | PostgreSQL 17 | Existing |
| ORM | asyncpg (raw SQL) | Performance |
| Auth | JWT + bcrypt | Simple, secure |
| Email | poplib, imaplib | Existing |
| Encryption | cryptography (Fernet) | API credentials |

### Multi-Tenancy Strategy

**Seçilen Yaklaşım:** Row-Level Tenancy with tenant_id

```sql
-- Her tabloda tenant_id
CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    ...
);

-- Index for performance
CREATE INDEX idx_emails_tenant ON emails(tenant_id);
```

**Neden Row-Level?**

- Basit implementasyon
- Tek database yeterli (başlangıç için)
- Query'lerde WHERE tenant_id = ? eklenmeli

### Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         PostgreSQL                               │
├─────────────────────────────────────────────────────────────────┤
│  tenants          users           tenant_settings                │
│  ├── id           ├── id          ├── tenant_id                 │
│  ├── name         ├── tenant_id   ├── booking_email_*           │
│  ├── slug         ├── email       ├── stopsale_email_*          │
│  └── created_at   ├── password    ├── sedna_url                 │
│                   └── role        ├── sedna_username (enc)      │
│                                   └── sedna_password (enc)      │
├─────────────────────────────────────────────────────────────────┤
│  emails (tenant_id)    reservations (tenant_id)                 │
│  stop_sales (tenant_id) processing_logs (tenant_id)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Epic ve Story Breakdown

### Epic 1: User Authentication (E1)

**Story Points:** 13  
**Sprint:** 1

| Story | SP | Description |
|-------|-----|-------------|
| E1-S1 | 3 | Database schema (tenants, users) |
| E1-S2 | 5 | Registration endpoint + UI |
| E1-S3 | 3 | Login/Logout + JWT |
| E1-S4 | 2 | Password reset flow |

### Epic 2: Tenant Settings (E2)

**Story Points:** 13  
**Sprint:** 1-2

| Story | SP | Description |
|-------|-----|-------------|
| E2-S1 | 3 | Settings database schema |
| E2-S2 | 5 | Settings UI (email, Sedna) |
| E2-S3 | 3 | Credential encryption |
| E2-S4 | 2 | Connection test with tenant credentials |

### Epic 3: Tenant-Aware Dashboard (E3)

**Story Points:** 8  
**Sprint:** 2

| Story | SP | Description |
|-------|-----|-------------|
| E3-S1 | 3 | Filter all queries by tenant_id |
| E3-S2 | 3 | Dashboard stats per tenant |
| E3-S3 | 2 | Protected routes (auth check) |

### Epic 4: Email Processing per Tenant (E4)

**Story Points:** 8  
**Sprint:** 2

| Story | SP | Description |
|-------|-----|-------------|
| E4-S1 | 3 | POP3 fetch with tenant credentials |
| E4-S2 | 3 | Store emails with tenant_id |
| E4-S3 | 2 | Email list filtered by tenant |

### Epic 5: Sedna Sync per Tenant (E5)

**Story Points:** 5  
**Sprint:** 3

| Story | SP | Description |
|-------|-----|-------------|
| E5-S1 | 3 | Sedna client with tenant credentials |
| E5-S2 | 2 | Reservation sync per tenant |

### Epic 6: Admin Dashboard (E6)

**Story Points:** 8  
**Sprint:** 3

| Story | SP | Description |
|-------|-----|-------------|
| E6-S1 | 3 | Admin role & permissions |
| E6-S2 | 3 | All tenants overview |
| E6-S3 | 2 | System health dashboard |

---

## 7. Roadmap

```
Sprint 1 (Week 1-2):
├── E1: User Authentication ━━━━━━━━━━━━━━━━━━━━━
└── E2-S1: Settings Schema ━━━━━━

Sprint 2 (Week 3-4):
├── E2-S2,S3,S4: Settings UI & Encryption ━━━━━━━
├── E3: Tenant Dashboard ━━━━━━━━━━━━━━━━
└── E4: Email Processing ━━━━━━━━━━━━━━━━

Sprint 3 (Week 5-6):
├── E5: Sedna Sync ━━━━━━━━━
├── E6: Admin Dashboard ━━━━━━━━━
└── Testing & Polish ━━━━━━━━━━━━━━

MVP Launch: Week 7
```

---

## 8. UI/UX Tasarım Hedefleri

### Design System

- **Theme:** Dark mode (mevcut)
- **Colors:** Emerald/Cyan gradient (mevcut)
- **Typography:** Inter font
- **Components:** Shadcn-style cards

### Key Screens

1. **Login/Register Page**
   - Clean, centered form
   - Logo + branding
   - Password visibility toggle

2. **Onboarding Wizard**
   - Step 1: Company info
   - Step 2: Email settings (booking)
   - Step 3: Email settings (stopsale)
   - Step 4: Sedna API credentials
   - Step 5: Connection test

3. **Dashboard**
   - Stats cards (existing)
   - Recent activity
   - Quick actions

4. **Settings Page**
   - Email configuration tabs
   - Sedna configuration
   - Test buttons

---

## 9. Risk Analizi

| Risk | Olasılık | Etki | Mitigasyon |
|------|----------|------|------------|
| Email provider blocks POP3 | Orta | Yüksek | IMAP fallback, OAuth support |
| Sedna API changes | Düşük | Yüksek | Version pinning, adapter pattern |
| Tenant data leak | Düşük | Kritik | Strict tenant_id filtering, audit |
| Scale issues | Orta | Orta | DB connection pooling, caching |
| User adoption | Orta | Orta | Onboarding wizard, documentation |

---

## 10. Success Metrics & KPIs

### Launch Metrics (MVP)

- [ ] 3 pilot tenant onboarded
- [ ] 0 critical bugs
- [ ] < 5s average email processing

### Growth Metrics (Month 3)

- [ ] 10+ active tenants
- [ ] 70% weekly active
- [ ] < 1% email processing error rate

### Business Metrics (Month 6)

- [ ] Break-even (if paid)
- [ ] NPS > 40
- [ ] < 5% churn

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Tenant | Bir acente/operatör hesabı |
| User | Tenant'a bağlı kullanıcı |
| Booking Email | Rezervasyon onay email'leri |
| Stop Sale | Satış durdurma bildirimleri |
| Sedna | Acente yönetim sistemi (3rd party) |

---

**Next Steps:**

1. Architecture document oluştur
2. Database schema detaylandır
3. API spec hazırla
4. E1-S1 ile geliştirmeye başla
