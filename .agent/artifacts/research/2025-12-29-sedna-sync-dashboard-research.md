# 🔬 Research: Sedna Sync Dashboard Implementation

> **Tarih:** 2025-12-29
> **Araştırmacı:** Dr. Elena Vasquez
> **Depth:** Deep
> **Confidence:** High

---

## 📋 Executive Summary

Entegrasyon projesinde email classification + Sedna sync için gerekli altyapı **büyük ölçüde mevcut**. Mevcut kod analizi, 3 ana servis (EmailFetch, Parser, Sedna) ve veritabanı tablolarının zaten uygun şekilde tasarlandığını gösteriyor. Eksik olan: manuel seçim ekranı + realtime progress + sync raporu.

**Tahmini geliştirme süresi:** 6-8 saat (altyapı hazır olduğu için)

---

## 🎯 Research Question

**Ana Soru:** Mevcut altyapı üzerine manuel email seçimi ve Sedna sync dashboard'u nasıl en verimli şekilde implemente edilir?

---

## 📊 Findings

### 1. Mevcut Altyapı Analizi

#### ✅ Veritabanı Tabloları (Hazır)

| Tablo | Kolonlar | Durumu |
|-------|----------|--------|
| `emails` | id, tenant_id, email_type, status, has_pdf, pdf_content, body_text | ✅ Mevcut |
| `reservations` | voucher_no, hotel_name, check_in/out, sedna_synced, source_email_id | ✅ Mevcut |
| `stop_sales` | hotel_name, date_from/to, is_close, sedna_synced | ✅ Mevcut |
| `pipeline_runs` | booking_emails_fetched, reservations_synced, errors | ✅ Mevcut |

#### ✅ Backend Servisleri (Hazır)

```
apps/api/
├── emailfetch/
│   ├── service.py        # ✅ OAuth2 IMAP fetch (91 email çekildi)
│   └── parser.py         # ✅ PDF + StopSale parsing
├── sedna/
│   ├── service.py        # ✅ sync_reservation(), sync_stop_sale(), sync_pending()
│   └── routes.py         # ✅ /api/sedna/sync/pending endpoint
└── processing/
    └── service.py        # ✅ Orchestration pipeline
```

#### ✅ Sedna API Endpoints (Hazır)

```python
# sedna/service.py - Mevcut Methodlar
async def sync_reservation(tenant_id, email_id) -> SyncResult
async def sync_stop_sale(tenant_id, stop_sale_id) -> SyncResult  
async def sync_pending(tenant_id) -> dict  # Bulk sync

# Sedna API Calls
POST /api/Reservation/InsertReservation  # ✅ Implemente
POST /api/StopSale/InsertStopSale        # ✅ Implemente
GET  /api/Shop/GetHotels                 # ✅ Hotel ID lookup
```

#### ⚠️ Eksik Parçalar

| Parça | Açıklama | Priority |
|-------|----------|----------|
| Bulk Sync API | Seçilen email ID'leri ile toplu sync | P0 |
| SSE Progress | Realtime ilerleme stream'i | P1 |
| Manual Selection UI | Checkbox'lı email listesi | P0 |
| Sync Report | Excel/PDF rapor indirme | P2 |

---

### 2. Email Classification Durumu

**Mevcut Sınıflandırma Logic:**

```python
# emailfetch/service.py - _classify_email()
booking_indicators = ["reservation", "booking", "voucher", "confirmation", "rezervasyon"]
stopsale_indicators = ["stop sale", "stopsale", "availability", "satış durdur"]

# Karar ağacı:
if indicator in subject/body → return type
elif has_pdf → return "booking"
else → return "unknown"
```

**Classification Accuracy Test:**

- 91 email çekildi
- 42 pending durumda (işlenmemiş)
- Classification doğruluğu: Test edilmeli

**Öneri:** Mevcut sınıflandırma yeterli görünüyor, ancak Juniper-specific patterns eklenebilir.

---

### 3. UI/UX Pattern Analysis

**Mevcut UI Yapısı:**

```
apps/web/src/app/
├── page.tsx              # Dashboard + Run Pipeline
├── emails/page.tsx       # Email listesi (readonly)
├── reservations/page.tsx # Rezervasyon listesi
├── stop-sales/page.tsx   # Stop sale listesi
└── settings/page.tsx     # Tenant ayarları
```

**Önerilen Yeni Sayfa:**

```
/emails/processing        # Manuel seçim + sync dashboard
```

**UI Önerileri:**

1. **Tab-based layout:** Reservations | Stop Sales | Unknown
2. **Card-based selection:** AG-Grid yerine okunabilir kartlar
3. **Bulk actions toolbar:** Select All + Sync Selected
4. **Progress modal:** SSE ile realtime güncellemeler

---

### 4. Realtime Progress: SSE vs WebSocket

| Kriter | SSE | WebSocket |
|--------|-----|-----------|
| Complexity | Düşük | Yüksek |
| Browser support | Excellent | Excellent |
| Bi-directional | ❌ Server→Client | ✅ |
| Reconnection | Otomatik | Manuel |
| FastAPI support | `StreamingResponse` | `websockets` lib |
| **Recommendation** | ✅ Tercih | Overkill |

**SSE Implementation:**

```python
# FastAPI SSE endpoint
from fastapi.responses import StreamingResponse

@router.get("/sync/{sync_id}/progress")
async def sync_progress(sync_id: str):
    async def event_generator():
        for i, item in enumerate(items):
            result = await process_item(item)
            yield f"data: {json.dumps(result)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 5. Implementasyon Planı

#### Phase 1: Backend APIs (2-3 saat)

```yaml
Dosyalar:
  - apps/api/sedna/bulk_sync.py  # Yeni: Bulk sync service
  - apps/api/routers/sync.py     # Yeni: Sync API endpoints

Endpoints:
  POST /api/sync/emails:
    body: { email_ids: number[] }
    response: { sync_id: string }
  
  GET /api/sync/{sync_id}/progress:
    response: SSE stream
    
  GET /api/sync/{sync_id}/result:
    response: { successful: [], failed: [], summary: {} }
    
  GET /api/sync/{sync_id}/report:
    query: { format: "excel" | "pdf" }
    response: File download
```

#### Phase 2: Frontend UI (3-4 saat)

```yaml
Dosyalar:
  - apps/web/src/app/emails/processing/page.tsx  # Ana sayfa
  - apps/web/src/components/SyncModal.tsx        # Sync dialog
  - apps/web/src/components/EmailProcessingCard.tsx  # Email kartı
  - apps/web/src/hooks/useSyncProgress.ts        # SSE hook

Features:
  - Tab'lı email listesi
  - Checkbox seçimi + Select All
  - Parsed data preview
  - Progress modal with SSE
  - Download report button
```

#### Phase 3: Polish & Testing (1-2 saat)

```yaml
Tasks:
  - Error handling improvements
  - Loading states
  - Empty states
  - Mobile responsive
  - E2E testing
```

---

## 💡 Recommendation

### Primary Recommendation

**Önerilen:** Mevcut altyapı üzerine incremental build - yeni dosyalar, mevcut servisler korunarak.

**Güven Seviyesi:** High

**Gerekçe:**

1. Sedna service, sync methodları zaten çalışıyor
2. Parser service, email→reservation dönüşümü yapıyor
3. Veritabanı şeması uygun
4. Sadece "seçim" ve "progress" katmanı eksik

### Implementation Priority

```
P0 (Must Have):
├── POST /api/sync/emails (bulk sync trigger)
├── GET /api/sync/{id}/progress (SSE)
├── /emails/processing page
└── Checkbox selection + Sync button

P1 (Should Have):
├── Success/failed detail modal
├── Retry failed items
└── Sync history list

P2 (Nice to Have):
├── Excel report download
├── Re-classify unknown emails
└── Edit parsed data before sync
```

### Risk/Consideration

⚠️ **Sedna API Rate Limits:** Throttling gerekebilir (5 req/sec önerilir)

⚠️ **Large Batches:** 100+ email sync uzun sürebilir - progress feedback kritik

⚠️ **Error Handling:** Her item için ayrı try-catch, batch failure önlenmeli

---

## 📚 Sources

1. **Kod Analizi** - `sedna/service.py`, `emailfetch/parser.py` - Tier 1
2. **Veritabanı Şeması** - PostgreSQL information_schema - Tier 1
3. **FastAPI SSE** - Official docs - Tier 1
4. **Mevcut UI** - `emails/page.tsx`, `page.tsx` - Tier 1

---

## 🏗️ Önerilen Dosya Yapısı

```
apps/api/
├── routers/
│   └── sync.py                    # NEW: Sync API endpoints
├── sedna/
│   ├── service.py                 # MEVCUT (kullanılacak)
│   ├── bulk_sync_service.py       # NEW: Orchestration + SSE
│   └── report_service.py          # NEW: Excel generation
└── main.py                        # MODIFY: Register sync router

apps/web/src/
├── app/
│   └── emails/
│       └── processing/
│           └── page.tsx           # NEW: Main processing page
├── components/
│   ├── SyncModal.tsx              # NEW: Progress dialog
│   └── EmailProcessingCard.tsx    # NEW: Selectable email card
└── hooks/
    └── useSyncProgress.ts         # NEW: SSE connection hook
```

---

## ✅ Sonraki Adımlar

1. **Hemen:** Backend bulk sync API implementasyonu
2. **Sonra:** Frontend processing sayfası
3. **Son:** Report download özelliği

**Tamamlanma tahmini:** 6-8 saat (tek oturumda mümkün)

---

*Research completed in 25 minutes*
*Dr. Elena Vasquez - Elite Deep Researcher*
