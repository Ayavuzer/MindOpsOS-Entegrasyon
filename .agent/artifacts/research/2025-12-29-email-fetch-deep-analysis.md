# 🔬 Research: Entegrasyon Email Fetch System - Deep Analysis

> **Tarih:** 2025-12-29
> **Araştırmacı:** Dr. Elena Vasquez
> **Depth:** Deep
> **Confidence:** High (Sorun çözüldü)

---

## 📋 Executive Summary

Entegrasyon projesinde OAuth2 IMAP e-posta çekme sistemi **başarıyla çalışır hale getirildi**. Toplamda **15+ farklı bug** tespit edilip düzeltildi. Kök neden: **veritabanı şema uyumsuzluğu** - kod `recipients`, `body_text`, `pdf_filename`, `pdf_content` kolonlarını bekliyordu ama veritabanında yoktu.

---

## 🎯 Research Question

**Ana Soru:** Neden OAuth2 IMAP ile bağlanıp e-postalar çekilemiyor ve tenant-specific konfigürasyon çalışmıyor?

**Alt Sorular:**

1. OAuth2 token flow doğru mu?
2. IMAP authentication başarılı mı?
3. E-postalar neden veritabanına kaydedilmiyor?
4. Her tenant kendi config'ini kullanabiliyor mu?

---

## 📊 Findings

### Tespit Edilen Hatalar ve Düzeltmeler

| # | Hata | Konum | Düzeltme | Versiyon |
|---|------|-------|----------|----------|
| 1 | IMAP scope eksik | `oauth/models.py` | `https://mail.google.com/` scope eklendi | v1.3.11 |
| 2 | Timezone karşılaştırma | `oauth/service.py` | `token_expiry.replace(tzinfo=None)` | v1.3.9 |
| 3 | timedelta import | `oauth/service.py` | Top-level import yapıldı | v1.3.8 |
| 4 | Tenant-specific OAuth | `oauth/service.py` | `_get_tenant_google_config()` eklendi | v1.3.7 |
| 5 | Timezone health service | `imap_idle/health_service.py` | Naive datetime karşılaştırma | v1.3.12 |
| 6 | Socket timeout | `emailfetch/service.py` | `socket.setdefaulttimeout(30)` | v1.3.13 |
| 7 | Liveness probe timeout | K8s Deployment | 60s timeout, 30s period | Runtime |
| 8 | Readiness probe timeout | K8s Deployment | 60s timeout, 30s period | Runtime |
| 9 | Stop sale config yanlış | Database | Host alanı temizlendi | Runtime |
| 10 | UNSEEN filter sorunu | `emailfetch/service.py` | Sadece SINCE filtresi kullan | v1.3.15 |
| 11 | errors list DB hatası | `processing/service.py` | `",".join(errors)` dönüşümü | v1.3.16 |
| 12 | email.policy import | `emailfetch/service.py` | `from email import policy` | v1.3.17 |
| 13 | **recipients kolonu yok** | Database | `ALTER TABLE ADD COLUMN` | Runtime |
| 14 | **body_text kolonu yok** | Database | `ALTER TABLE ADD COLUMN` | Runtime |
| 15 | **pdf_filename/content yok** | Database | `ALTER TABLE ADD COLUMN` | Runtime |
| 16 | pipeline_runs kolonları | Database | booking_emails_fetched vb. eklendi | Runtime |

### Kök Neden Analizi

```
                    ┌─────────────────────────────────────────┐
                    │  UI: "Run Pipeline" tıklandı            │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │  POST /api/processing/run               │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │  ProcessingService.run_full_pipeline()  │
                    └──────────────────┬──────────────────────┘
                                       │
                    ┌──────────────────▼──────────────────────┐
                    │  TenantEmailService.fetch_emails()      │
                    └──────────────────┬──────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
    ┌──────▼──────┐            ┌───────▼───────┐           ┌───────▼───────┐
    │ _get_config │            │ _refresh_token │           │ _fetch_oauth  │
    └──────┬──────┘            └───────┬───────┘           └───────┬───────┘
           │                           │                           │
           │ ✅ Çalışıyor              │ ✅ Çalışıyor              │ ✅ Çalışıyor
           │                           │                           │
    ┌──────▼──────────────────────────────────────────────────────▼───────┐
    │                    _process_imap_emails()                           │
    └─────────────────────────────────┬───────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │  INSERT INTO emails (...)         │
                    │                                   │
                    │  ❌ "recipients" kolonu YOK!      │
                    │  ❌ "body_text" kolonu YOK!       │
                    │  ❌ "pdf_filename" kolonu YOK!    │
                    │  ❌ "pdf_content" kolonu YOK!     │
                    └───────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────┐
                    │  Exception yakalandı              │
                    │  result.errors.append(...)        │
                    │  emails_new = 0 kaldı             │
                    └───────────────────────────────────┘
```

### Multi-Tenant Architecture Review

```python
# ✅ DOĞRU: Tenant-specific OAuth config
async def _get_tenant_google_config(self, tenant_id: int):
    """Get tenant's Google OAuth credentials from database."""
    async with self.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT google_client_id, google_client_secret_encrypted
            FROM tenant_settings WHERE tenant_id = $1
            """, tenant_id
        )
    # Returns TenantGoogleOAuthConfig with tenant's own credentials

# ✅ DOĞRU: Token refresh tenant-specific
async def refresh_google_token(self, tenant_id: int, email_type: str):
    google_config = await self._get_tenant_google_config(tenant_id)
    # Uses tenant's client_id/client_secret for refresh

# ✅ DOĞRU: Email fetch tenant-isolated
async def fetch_emails(self, tenant_id: int, email_type: str):
    config = await self._get_email_config(tenant_id, email_type)
    # Fetches config from tenant_settings table with tenant_id filter
```

---

## 🏗️ Architecture Improvements Needed

### 1. Database Migration System

**Problem:** Manuel kolon ekleme gerekiyor - production'da riskli.

**Öneri:**

```python
# migrations/001_add_email_columns.py
async def upgrade(conn):
    await conn.execute("""
        ALTER TABLE emails 
        ADD COLUMN IF NOT EXISTS recipients TEXT[],
        ADD COLUMN IF NOT EXISTS body_text TEXT,
        ADD COLUMN IF NOT EXISTS pdf_filename VARCHAR(255),
        ADD COLUMN IF NOT EXISTS pdf_content BYTEA
    """)

async def downgrade(conn):
    # Rollback logic
```

### 2. Error Visibility

**Problem:** Hatalar sessizce yakalanıp kayboluyor.

**Öneri:**

```python
# Before
except Exception as e:
    result.errors.append(f"Email {num}: {str(e)}")

# After  
except Exception as e:
    import logging
    logging.error(f"Email {num} failed: {e}", exc_info=True)
    result.errors.append(f"Email {num}: {str(e)}")
```

### 3. Schema Validation on Startup

**Öneri:**

```python
# main.py - startup event
@app.on_event("startup")
async def validate_schema():
    required_columns = {
        "emails": ["recipients", "body_text", "pdf_filename", "pdf_content"],
        "pipeline_runs": ["booking_emails_fetched", "stopsale_emails_fetched"]
    }
    
    for table, columns in required_columns.items():
        for col in columns:
            exists = await check_column_exists(table, col)
            if not exists:
                raise RuntimeError(f"Missing column: {table}.{col}")
```

---

## 💡 Recommendation

### Primary Recommendation

**Önerilen:** Şu an sistem ÇALIŞIR durumda. Aşağıdaki iyileştirmeler yapılmalı:

1. ✅ **Acil:** Veritabanı migration script oluştur
2. ✅ **Acil:** Error logging'i güçlendir  
3. 📋 **Kısa vadeli:** Schema validation on startup
4. 📋 **Orta vadeli:** Alembic veya benzeri migration tool

**Güven Seviyesi:** High

### Test Sonuçları

| Test | Sonuç |
|------|-------|
| OAuth2 token refresh | ✅ Çalışıyor |
| IMAP XOAUTH2 auth | ✅ Çalışıyor |
| Email fetch (91 email) | ✅ Çalışıyor |
| Database insert | ✅ Çalışıyor |
| Tenant isolation | ✅ Çalışıyor |

### Mevcut Tenant Durumu

| Tenant | Booking | StopSale |
|--------|---------|----------|
| 4 | password (unconfigured) | password (unconfigured) |
| 5 | **OAuth2 ✅** (<alyavuzer@gmail.com>) | password |
| 7 | OAuth2 (<yavuzer07aykut@gmail.com>) | OAuth2 |

---

## 📚 Sources

1. **Kod Analizi** - `emailfetch/service.py`, `oauth/service.py`, `processing/service.py` - Tier 1
2. **Runtime Debug** - kubectl exec ile canlı test - Tier 1
3. **Database Schema** - information_schema.columns sorgusu - Tier 1

---

## ⚠️ Risk/Consideration

1. **Token Expiry:** Token 1 saat geçerli - refresh job'ı 5dk önce yeniliyor (✅ OK)
2. **Rate Limiting:** Gmail IMAP rate limitleri olabilir - 100 email/batch limiti var (✅ OK)
3. **Memory:** Büyük PDF'ler memory sorununa yol açabilir - streaming düşünülmeli
4. **Timezone:** UTC kullanılıyor - Türkiye için +3 offset dikkat edilmeli

---

## 🎯 Action Items

- [x] Veritabanı eksik kolonları ekle
- [x] OAuth2 IMAP scope düzelt
- [x] Timezone karşılaştırmalarını düzelt
- [x] Socket timeout ekle
- [x] K8s probe timeout'larını artır
- [x] Email policy import düzelt
- [ ] Migration script oluştur (önerilen)
- [ ] Error logging güçlendir (önerilen)
- [ ] Schema validation ekle (önerilen)

---

*Research completed in 45 minutes*
*Final Status: ✅ PROBLEM SOLVED - 91 emails successfully fetched*
