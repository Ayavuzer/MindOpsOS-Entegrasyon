# E5: Sedna API Authentication Fix - Architecture

> **Epic:** E5
> **Tarih:** 2025-12-29
> **Status:** Ready for Development

---

## 📋 Overview

Bu döküman E5 epic'inin teknik implementasyon detaylarını içerir.

---

## 🔧 Technical Changes

### 1. Authentication Pattern

Mevcut projede kullanılan Sedna auth pattern:

```python
# Pattern: Query String Authentication
params={
    "username": sedna_config["username"],
    "password": sedna_config["password"],
}
```

Bu pattern şu endpoint'lerde **zaten kullanılıyor:**

- `InsertReservation` (Line 141-144) ✅
- `GetHotels` (Line 463-466) ✅

Bu pattern'i **eksik olan yerlere** ekle:

- `UpdateStopSale` Phase 1 (Line 278-281) ❌ → Fix
- `UpdateStopSale` Phase 2 (Line 316-319) ❌ → Fix

---

## 📁 Files to Modify

### 1. apps/api/sedna/service.py

**Change 1: Phase 1 Authentication (Line 278-281)**

```python
# BEFORE:
response1 = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase1_payload,
)

# AFTER:
response1 = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase1_payload,
    params={
        "username": sedna_config["username"],
        "password": sedna_config["password"],
    },
)
```

**Change 2: Phase 2 Authentication (Line 316-319)**

```python
# BEFORE:
response2 = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase2_payload,
)

# AFTER:
response2 = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase2_payload,
    params={
        "username": sedna_config["username"],
        "password": sedna_config["password"],
    },
)
```

### 2. Database Migration (SQL)

```sql
-- E5.S2: Tenant Settings Configuration
UPDATE tenant_settings 
SET 
  sedna_operator_id = 571,
  sedna_operator_code = '7STAR'
WHERE id = 1;
```

---

## 🧪 Testing Strategy

### Unit Test (Manual)

```python
# Test authentication params are included
import httpx

async def test_stop_sale_auth():
    sedna_config = {
        "api_url": "http://test.kodsedna.com/SednaAgencyb2bApi",
        "username": "7STAR",
        "password": "7STAR",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
            json={"RecId": 0},  # Minimal test payload
            params={
                "username": sedna_config["username"],
                "password": sedna_config["password"],
            },
        )
        
        # 401 = Auth failed (wrong creds or endpoint)
        # 400 = Bad request (auth worked, payload invalid)
        # 200 = Success
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
```

### Integration Test

1. Email #260 seç
2. "Sync Selected" tıkla
3. Beklenen: Artık 401 değil, farklı bir hata veya başarı

---

## 📊 API Endpoints Summary

| Endpoint | Method | Auth Required | Current Status |
|----------|--------|---------------|----------------|
| `/api/Reservation/InsertReservation` | POST | ✅ params | ✅ Working |
| `/api/Contract/UpdateStopSale` | PUT | ✅ params | ❌ Missing → Fix |
| `/api/Shop/GetHotels` | GET | ✅ params | ✅ Working |

---

## 🔄 Deployment

```bash
# 1. Build & Deploy API
docker buildx build --platform linux/amd64 \
  -t ghcr.io/ayavuzer/entegrasyon-api:v1.8.0-auth-fix \
  --push .

# 2. Update K8s
kubectl set image deployment/entegrasyon-api \
  api=ghcr.io/ayavuzer/entegrasyon-api:v1.8.0-auth-fix \
  -n entegrasyon

# 3. Apply DB Migration
kubectl exec -n entegrasyon deploy/entegrasyon-api -- python -c "
import asyncio
import asyncpg
import os

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    await conn.execute('''
        UPDATE tenant_settings 
        SET sedna_operator_id = 571, sedna_operator_code = '7STAR'
        WHERE id = 1
    ''')
    print('Tenant settings updated')
    await conn.close()

asyncio.run(main())
"
```

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Endpoint path yanlış | Sync hala çalışmaz | E5.S3'te alternatif path'leri test et |
| Password yanlış | 401 devam eder | Tenant ile credential doğrula |
| Sedna API down | Test edilemez | Retry daha sonra |

---

## ✅ Definition of Done

- [ ] E5.S1: Auth params eklendi
- [ ] E5.S2: Tenant settings güncellendi
- [ ] E5.S3: Endpoint path doğrulandı
- [ ] E5.S4: E2E test geçti
- [ ] API deployed: v1.8.0-auth-fix
- [ ] Email #260 sync başarılı

---

*Architecture document created: 2025-12-29*
