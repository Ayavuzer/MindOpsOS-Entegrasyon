# E5: Sedna API Authentication Fix

> **Epic ID:** E5
> **Priority:** P0 (Critical)
> **Estimated SP:** 5
> **Status:** Ready for Development
> **Created:** 2025-12-29

---

## 📋 Epic Summary

Sedna API entegrasyonunda tespit edilen authentication ve endpoint sorunlarını düzelt. Stop Sale ve Rezervasyon sync işlemlerinin başarılı şekilde tamamlanmasını sağla.

---

## 🎯 Goals

1. Stop Sale sync işlemlerinde HTTP 401 hatasını çöz
2. Tüm Sedna API çağrılarında tutarlı authentication sağla
3. Endpoint path'lerini doğrula ve düzelt
4. Tenant settings'te eksik Sedna konfigürasyonlarını tamamla

---

## 📊 Background & Context

### Problem Statement

Research analizi (`2025-12-29-sedna-api-integration-analysis.md`) sonucunda tespit edilen sorunlar:

1. **Authentication Eksikliği:**
   - Reservation API'de `params` ile auth gönderiliyor ✅
   - Stop Sale API'de `params` **EKSİK** ❌
   - Bu HTTP 401 hatasına neden oluyor

2. **Endpoint Path Belirsizliği:**
   - Mevcut kod: `/api/Contract/UpdateStopSale`
   - Postman collection'da bu endpoint YOK
   - Doğru path: `/Integratiion/...` olabilir (çift 'i' ile!)

3. **Tenant Settings Eksik:**
   - `sedna_operator_id`: null
   - `sedna_operator_code`: null

### Current State

```python
# Mevcut kod (YANLIŞ):
response = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase1_payload,
)  # ← params YOK!
```

### Desired State

```python
# Olması gereken:
response = await client.put(
    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
    json=phase1_payload,
    params={
        "username": sedna_config["username"],
        "password": sedna_config["password"],
    },
)
```

---

## 📝 Stories

### E5.S1: Stop Sale API Authentication Fix

**Story ID:** E5.S1
**SP:** 2
**Priority:** P0
**Type:** Bug Fix

**Description:**
Stop Sale sync işleminde `UpdateStopSale` endpoint'ine authentication parametrelerini ekle.

**Acceptance Criteria:**

- [ ] Phase 1 API çağrısına `params` ile username/password ekle (Line 278-281)
- [ ] Phase 2 API çağrısına `params` ile username/password ekle (Line 316-319)
- [ ] GetHotels endpoint'inde mevcut auth pattern'ini takip et
- [ ] Local test ile 401 hatası kayboldu doğrula

**Technical Notes:**

```python
params={
    "username": sedna_config["username"],
    "password": sedna_config["password"],
}
```

**Files to Modify:**

- `apps/api/sedna/service.py` (Lines 278-281, 316-319)

---

### E5.S2: Tenant Settings Configuration

**Story ID:** E5.S2
**SP:** 1
**Priority:** P0
**Type:** Configuration

**Description:**
Tenant settings'te eksik Sedna konfigürasyonlarını tamamla.

**Acceptance Criteria:**

- [ ] `sedna_operator_id` = 571 ayarla
- [ ] `sedna_operator_code` = '7STAR' ayarla
- [ ] Settings UI'da bu alanları görüntüle/düzenle

**SQL:**

```sql
UPDATE tenant_settings 
SET 
  sedna_operator_id = 571,
  sedna_operator_code = '7STAR'
WHERE id = 1;
```

---

### E5.S3: Endpoint Path Validation

**Story ID:** E5.S3
**SP:** 1
**Priority:** P1
**Type:** Investigation

**Description:**
Sedna API endpoint path'lerini doğrula. 404 alınırsa alternatif path'leri test et.

**Acceptance Criteria:**

- [ ] `/api/Contract/UpdateStopSale` endpoint'ini test et
- [ ] 404 alınırsa `/Integratiion/SaveStopSale` dene
- [ ] Doğru endpoint'i dokümante et
- [ ] Gerekirse kod güncellemesi yap

**Test Cases:**

```bash
# Test 1: Mevcut endpoint
curl -X PUT "http://test.kodsedna.com/SednaAgencyb2bApi/api/Contract/UpdateStopSale?username=7STAR&password=7STAR" \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Test 2: Alternatif endpoint (404 alınırsa)
curl -X POST "http://test.kodsedna.com/SednaAgencyb2bApi/Integratiion/SaveStopSale?username=7STAR&password=7STAR" \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

---

### E5.S4: End-to-End Sync Test

**Story ID:** E5.S4
**SP:** 1
**Priority:** P1
**Type:** Testing

**Description:**
Stop Sale ve Reservation sync işlemlerini end-to-end test et.

**Acceptance Criteria:**

- [ ] Email #260 (Mandarin Resort) stop sale sync başarılı
- [ ] Sedna'da kayıt oluşturulduğunu doğrula
- [ ] Hotel Selection Modal çalışıyor
- [ ] Retry Failed butonu çalışıyor

---

## 📊 Story Points Summary

| Story | SP | Priority | Type |
|-------|:--:|----------|------|
| E5.S1 | 2 | P0 | Bug Fix |
| E5.S2 | 1 | P0 | Configuration |
| E5.S3 | 1 | P1 | Investigation |
| E5.S4 | 1 | P1 | Testing |
| **Total** | **5** | | |

---

## 🔗 Dependencies

- E4 (Hotel Fuzzy Match) - ✅ Completed
- Sedna test API credentials - ✅ Available

---

## 📚 References

- Research: `.agent/artifacts/research/2025-12-29-sedna-api-integration-analysis.md`
- Sedna API Analysis: `docs/sedna-api-analysis.md`
- Service Code: `apps/api/sedna/service.py`

---

*Epic created: 2025-12-29*
