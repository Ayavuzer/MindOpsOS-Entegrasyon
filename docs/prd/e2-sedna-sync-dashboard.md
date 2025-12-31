# PRD: Sedna Sync Dashboard (E2: Email Processing)

> **Versiyon:** 1.0
> **Tarih:** 2025-12-29
> **Durum:** Draft
> **Epic:** E2 - Email Processing & Sedna Sync

---

## 1. Goals and Background

### 1.1 Problem Statement

Entegrasyon sistemi şu anda e-postaları otomatik olarak çekiyor (✅ 91 email) ancak:

- Kullanıcılar hangi e-postaların reservation/stopsale olarak sınıflandırıldığını göremiyorlar
- Manuel seçim yaparak Sedna'ya sync yapmak mümkün değil
- Sync sonuçlarını (başarılı/başarısız) takip edecek bir rapor yok

### 1.2 Goals

| Goal | Metric | Target |
|------|--------|--------|
| Manuel Seçim | Kullanıcı seçebilir mi? | 100% kontrol |
| Sync Visibility | Sync durumu görünür mü? | Realtime progress |
| Error Tracking | Hatalar açıklanıyor mu? | Actionable error messages |
| Reporting | Rapor indirilebilir mi? | Excel format |

### 1.3 Target Users

| User Type | Need |
|-----------|------|
| Operasyon Personeli | Reservation/Stop Sale seçimi ve Sedna'ya aktarım |
| Yönetici | Sync geçmişi ve raporları inceleme |

### 1.4 Success Metrics

- [ ] Email'lerin %100'ü görüntülenebilir
- [ ] Seçilen item'ların %95+'ı başarıyla sync edilir
- [ ] Sync süresi <30 saniye (100 item için)
- [ ] Kullanıcı memnuniyeti: "Kolay kullanılıyor" (%80+)

---

## 2. Detailed Requirements

### 2.1 Functional Requirements

#### FR1: Email Classification Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1.1 | Sistem, reservation/stopsale/unknown olarak sınıflandırılmış e-postaları tab'lı arayüzde göstermeli | P0 |
| FR1.2 | Her email için özet bilgi kartı görüntülenmeli (subject, sender, parsed data) | P0 |
| FR1.3 | Kullanıcı birden fazla email seçebilmeli (checkbox) | P0 |
| FR1.4 | "Select All" butonu ile tüm görünür item'lar seçilebilmeli | P1 |
| FR1.5 | Unknown email'ler manuel olarak re-classify edilebilmeli | P2 |

#### FR2: Sedna Sync İşlemi

| ID | Requirement | Priority |
|----|-------------|----------|
| FR2.1 | "Sync to Sedna" butonu seçili email'leri senkronize etmeli | P0 |
| FR2.2 | Sync öncesi doğrulama modalı gösterilmeli (kaç item seçili?) | P1 |
| FR2.3 | Sync sırasında realtime progress bar gösterilmeli | P0 |
| FR2.4 | Her item için success/failed durumu anlık gösterilmeli | P0 |
| FR2.5 | Failed item'lar için "Retry" butonu olmalı | P1 |
| FR2.6 | Failed item'lar için error message görüntülenmeli | P0 |

#### FR3: Sync Raporlama

| ID | Requirement | Priority |
|----|-------------|----------|
| FR3.1 | Sync tamamlandığında özet rapor gösterilmeli | P0 |
| FR3.2 | Rapor Excel formatında indirilebilmeli | P2 |
| FR3.3 | Son 20 sync işlemi "History" bölümünde listelenebilmeli | P1 |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Email listesi 2 saniyede yüklenmeli | <2s |
| NFR2 | 100 item sync <30s tamamlanmalı | <30s |
| NFR3 | Arayüz mobile responsive olmalı | 320px+ |
| NFR4 | Multi-tenant isolation korunmalı | Zorunlu |

---

## 3. UI Design Goals

### 3.1 Core Screens

#### Screen 1: Email Processing Dashboard (`/emails/processing`)

```
┌─────────────────────────────────────────────────────────────┐
│  Email Processing                              [🔄 Refresh] │
├─────────────────────────────────────────────────────────────┤
│  📊 Stats: 42 Pending | 156 Processed | 3 Failed           │
├─────────────────────────────────────────────────────────────┤
│  [Tabs] Reservations (28) | Stop Sales (14) | Unknown (0)  │
├─────────────────────────────────────────────────────────────┤
│  [☑] Select All                  [🚀 Sync Selected (15)]   │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [☑] | 📧 Reservation #12345                          │  │
│  │     | From: juniper@example.com                      │  │
│  │     | Hotel: Grand Resort | Check-in: 2025-01-15     │  │
│  │     | [📄 PDF] [✏️ Edit] [🔄 Sync]                   │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [☑] | 📧 Stop Sale - Grand Resort                    │  │
│  │     | Dates: 2025-02-01 - 2025-02-15                 │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Recent Sync History                          [View All]    │
│  • 17:00 | ✅ 15 synced | ❌ 2 failed | ⏱️ 4.2s            │
└─────────────────────────────────────────────────────────────┘
```

#### Screen 2: Sync Progress Modal

```
┌─────────────────────────────────────────────────┐
│  Syncing to Sedna                          [X]  │
├─────────────────────────────────────────────────┤
│  Progress: ████████░░░░ 60% (9/15)              │
│                                                 │
│  Current: Reservation #12345...                 │
│                                                 │
│  Results:                                       │
│  ✅ Reservation #12340 → Sedna: RES-5678       │
│  ✅ Reservation #12341 → Sedna: RES-5679       │
│  ❌ Reservation #12342 → Error: Guest required │
└─────────────────────────────────────────────────┘
```

#### Screen 3: Sync Complete Modal

```
┌─────────────────────────────────────────────────┐
│  Sync Complete ✅                          [X]  │
├─────────────────────────────────────────────────┤
│  Summary:                                       │
│  ✅ Successful: 13                              │
│  ❌ Failed: 2                                   │
│  ⏱️ Duration: 4.2s                              │
│                                                 │
│  Failed Items:                                  │
│  • Reservation #12342: Guest name required      │
│  • Stop Sale #SS-001: Hotel not found in Sedna │
│                                                 │
│  [📥 Download Report]  [🔄 Retry Failed] [Close]│
└─────────────────────────────────────────────────┘
```

### 3.2 Design System

```yaml
Colors:
  Primary: Emerald (brand color)
  Success: Green (#10B981)
  Error: Red (#EF4444)
  Warning: Yellow (#F59E0B)
  Background: Slate-900 (dark theme)

Typography:
  Font: Inter (Google Fonts)
  Sizes: 14px base, 16px headers

Components:
  Buttons: Rounded-lg, gradient backgrounds
  Cards: Border slate-800, hover effect
  Tabs: Underline active state
```

---

## 4. Technical Assumptions

### 4.1 Existing Infrastructure (Reuse)

| Component | File | Status |
|-----------|------|--------|
| Email Fetch | `emailfetch/service.py` | ✅ Çalışıyor |
| Email Parser | `emailfetch/parser.py` | ✅ Çalışıyor |
| Sedna Sync | `sedna/service.py` | ✅ Çalışıyor |
| Processing Pipeline | `processing/service.py` | ✅ Çalışıyor |
| Reservations Table | PostgreSQL | ✅ Mevcut |
| Stop Sales Table | PostgreSQL | ✅ Mevcut |

### 4.2 New Components (Build)

| Component | File | Purpose |
|-----------|------|---------|
| Bulk Sync Service | `sedna/bulk_sync_service.py` | Orchestration + SSE |
| Sync Router | `routers/sync.py` | API endpoints |
| Report Service | `sedna/report_service.py` | Excel generation |
| Processing Page | `emails/processing/page.tsx` | Main UI |
| Sync Modal | `components/SyncModal.tsx` | Progress dialog |
| SSE Hook | `hooks/useSyncProgress.ts` | Realtime updates |

### 4.3 API Design

```yaml
POST /api/sync/emails:
  description: Start bulk sync
  body: { email_ids: number[] }
  response: { sync_id: string }

GET /api/sync/{sync_id}/progress:
  description: SSE stream for realtime progress
  response: Server-Sent Events stream
  events:
    - { type: "progress", data: { current, total, item } }
    - { type: "complete", data: { summary } }

GET /api/sync/{sync_id}/result:
  description: Final sync results
  response: { successful: [], failed: [], summary: {} }

GET /api/sync/{sync_id}/report:
  description: Download Excel report
  query: { format: "excel" }
  response: File download
```

---

## 5. Epic & Story Breakdown

### Epic 2: Email Processing & Sedna Sync

**Total Story Points:** 21 SP
**Estimated Duration:** 6-8 hours

---

### Story E2.S1: Backend Bulk Sync API

**Points:** 5 SP
**Priority:** P0

**Description:**
Seçilen email ID'leri alarak toplu Sedna sync işlemi başlatan API endpoint'i oluştur.

**Acceptance Criteria:**

- [ ] POST /api/sync/emails endpoint'i çalışıyor
- [ ] Sync ID üretiliyor ve dönülüyor
- [ ] Background task olarak çalışıyor
- [ ] Her item için sync_reservation/sync_stop_sale çağrılıyor
- [ ] Sonuçlar database'e kaydediliyor

**Technical Notes:**

```python
# sedna/bulk_sync_service.py
async def start_bulk_sync(tenant_id: int, email_ids: list[int]) -> str:
    sync_id = generate_sync_id()
    # Store sync job in database
    # Return sync_id immediately
    # Process in background
    return sync_id
```

---

### Story E2.S2: SSE Progress Stream

**Points:** 3 SP
**Priority:** P0

**Description:**
Sync ilerlemesini realtime olarak stream eden SSE endpoint'i.

**Acceptance Criteria:**

- [ ] GET /api/sync/{sync_id}/progress SSE stream dönüyor
- [ ] Her item işlendiğinde event gönderiliyor
- [ ] Event format: { current, total, item, status }
- [ ] Tamamlandığında "complete" event gönderiliyor
- [ ] Frontend'de EventSource ile dinlenebiliyor

**Technical Notes:**

```python
from fastapi.responses import StreamingResponse

@router.get("/sync/{sync_id}/progress")
async def sync_progress(sync_id: str):
    async def event_generator():
        while True:
            event = await get_next_event(sync_id)
            if event:
                yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "complete":
                break
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### Story E2.S3: Processing Dashboard Page

**Points:** 5 SP
**Priority:** P0

**Description:**
/emails/processing sayfası - tab'lı email listesi, checkbox seçimi.

**Acceptance Criteria:**

- [ ] Sayfa /emails/processing route'unda erişilebilir
- [ ] 3 tab: Reservations, Stop Sales, Unknown
- [ ] Her email için kart görünümü
- [ ] Checkbox ile seçim yapılabiliyor
- [ ] Select All / Deselect All çalışıyor
- [ ] "Sync Selected" butonu aktif (seçim varsa)

**Technical Notes:**

- React state ile selection yönetimi
- useEffect ile email fetch
- Mevcut EmailCard pattern kullan

---

### Story E2.S4: Sync Modal Component

**Points:** 5 SP
**Priority:** P0

**Description:**
Sync progress modal - SSE ile realtime güncellemeler.

**Acceptance Criteria:**

- [ ] Modal açıldığında SSE bağlantısı kuruluyor
- [ ] Progress bar güncelleniyor
- [ ] Başarılı item'lar yeşil tick ile gösteriliyor
- [ ] Başarısız item'lar kırmızı X ile + error message
- [ ] Tamamlandığında özet gösteriliyor
- [ ] "Retry Failed" butonu çalışıyor

**Technical Notes:**

```typescript
// hooks/useSyncProgress.ts
export function useSyncProgress(syncId: string) {
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [results, setResults] = useState<SyncResult[]>([]);
  
  useEffect(() => {
    const eventSource = new EventSource(`/api/sync/${syncId}/progress`);
    eventSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      // Update state
    };
    return () => eventSource.close();
  }, [syncId]);
  
  return { progress, results };
}
```

---

### Story E2.S5: Sync Result & Report

**Points:** 3 SP
**Priority:** P1

**Description:**
Sync sonuç modal + Excel rapor indirme.

**Acceptance Criteria:**

- [ ] Sync tamamlandığında özet modal gösteriliyor
- [ ] Başarılı/Başarısız sayıları görünüyor
- [ ] "Download Report" Excel dosyası indiriyor
- [ ] Excel'de: Summary sheet, Successful sheet, Failed sheet

**Technical Notes:**

```python
# sedna/report_service.py
from openpyxl import Workbook

def generate_sync_report(sync_id: str) -> bytes:
    wb = Workbook()
    # Summary sheet
    # Successful items sheet
    # Failed items sheet
    return save_to_bytes(wb)
```

---

## 6. Dependency Graph

```
E2.S1 (Backend Bulk Sync)
    │
    └─► E2.S2 (SSE Progress)
            │
            └─► E2.S4 (Sync Modal)
                    │
                    └─► E2.S5 (Sync Report)

E2.S3 (Processing Page) ───► E2.S4 (Sync Modal)
```

---

## 7. Out of Scope (v2.0)

| Feature | Reason |
|---------|--------|
| PDF editor | Complexity - future enhancement |
| Batch re-classification | Research needed |
| Scheduled sync | Cron job infrastructure needed |
| Webhook notifications | External integration |

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sedna API rate limits | Sync yavaşlar | Throttling (5 req/sec) |
| Large batch timeout | UI hang | SSE + background processing |
| Hotel not found | Sync fails | Pre-validation + manual mapping |

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-29 | 1.0 | Initial PRD draft |

---

*Document Owner: Product Team*
*Technical Review: Engineering Team*
