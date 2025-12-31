# 🔬 Research Prompt: Email Classification & Sedna API Sync Dashboard

> **Priscilla's Optimized Prompt**
> **Optimization Level:** Production
> **Ambiguity Score:** 15/100 (Well-defined after optimization)

---

## 📋 Task Summary

**Implement:** Email Processing Dashboard with automatic Stop Sale / Reservation classification and Sedna API sync with manual review capability.

---

## 🎯 Context

### Project Information

| Key | Value |
|-----|-------|
| **Project** | MindOps Entegrasyon |
| **Backend** | FastAPI, Python 3.11, asyncpg |
| **Frontend** | Next.js 14, React 18, TypeScript |
| **Database** | PostgreSQL (multi-tenant) |
| **API Integration** | Sedna Agency ERP |
| **Current State** | Emails fetched (91) ✅, classification exists |

### Existing Infrastructure

```
apps/api/
├── emailfetch/service.py      # ✅ Email fetch with OAuth2 IMAP
├── processing/service.py      # ✅ Pipeline orchestration
├── sedna/service.py           # ✅ Sedna API client
├── tenant/service.py          # ✅ Multi-tenant config
└── parser/service.py          # ✅ Email parsing (needs enhancement)

apps/web/src/app/
├── page.tsx                   # Dashboard with Run Pipeline
├── emails/page.tsx            # Email list (basic)
├── reservations/page.tsx      # Reservation list (basic)
└── settings/page.tsx          # Tenant settings
```

### Current Sedna API Endpoints (from sedna/service.py)

```python
# POST /api/reservations - Create reservation
# POST /api/stop-sales - Create stop sale
# GET /api/reservations/{id} - Get reservation
# GET /api/stop-sales/{id} - Get stop sale
```

---

## 📝 Detailed Requirements

### R1: Automatic Email Classification

**Problem:** Emails are classified during fetch but classification accuracy is low.

**Requirement:**

```yaml
Classification Types:
  - reservation: Booking confirmation, voucher, PDF with reservation data
  - stopsale: Stop sale notification, availability closure
  - unknown: Cannot determine type

Enhanced Classification Rules:
  Reservation Indicators:
    Subject Keywords:
      - "Reservation Confirmation"
      - "Booking Voucher"
      - "Konaklama Onay"
      - "Rezervasyon"
      - "Reservation No:"
    Body Keywords:
      - "Guest Name:"
      - "Check-in:"
      - "Check-out:"
      - "Room Type:"
      - "Confirmation Number:"
    Attachments:
      - PDF with "voucher" in filename
      - PDF with reservation table patterns
  
  Stop Sale Indicators:
    Subject Keywords:
      - "Stop Sale"
      - "Close Out"
      - "Satış Durdurma"
      - "Availability Update"
    Body Keywords:
      - "Stop Sale Period:"
      - "Close out from"
      - "Room type blocked"
```

**Success Criteria:**

- [ ] Classification accuracy > 90% for Juniper emails
- [ ] Unknown < 10% of total emails
- [ ] Classification time < 100ms per email

---

### R2: Email Processing Dashboard (NEW PAGE)

**Route:** `/emails/processing`

**UI Mockup:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Email Processing Dashboard                                    [Refresh]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   Pending       │  │   Processed     │  │   Failed        │         │
│  │      42         │  │      156        │  │       3         │         │
│  │   📧 Emails     │  │   ✅ Success    │  │   ❌ Error      │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ [Tabs]  Reservations (28)  |  Stop Sales (14)  |  Unknown (0)      │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │                                                                     │ │
│ │  [☑] Select All                      [🚀 Sync Selected to Sedna]   │ │
│ │                                                                     │ │
│ │  ┌───────────────────────────────────────────────────────────────┐ │ │
│ │  │ [☑] │ 📧 Reservation Confirmation #12345                      │ │ │
│ │  │     │ From: reservations@juniper.com                          │ │ │
│ │  │     │ Date: 2025-12-28 14:30                                  │ │ │
│ │  │     │ Guest: John Doe | Check-in: 2025-01-15 | 3 nights       │ │ │
│ │  │     │ Hotel: Grand Resort | Room: Double Deluxe               │ │ │
│ │  │     │ Status: [Pending] [📄 View PDF] [✏️ Edit] [🗑️ Delete]   │ │ │
│ │  └───────────────────────────────────────────────────────────────┘ │ │
│ │                                                                     │ │
│ │  ┌───────────────────────────────────────────────────────────────┐ │ │
│ │  │ [☑] │ 📧 Reservation Confirmation #12346                      │ │ │
│ │  │     │ ...                                                     │ │ │
│ │  └───────────────────────────────────────────────────────────────┘ │ │
│ │                                                                     │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ Sync History                                            [View All]  │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │  2025-12-29 17:00 | ✅ 15 synced | ❌ 2 failed | ⏱️ 4.2s         │ │
│ │  2025-12-29 16:30 | ✅ 8 synced  | ❌ 0 failed | ⏱️ 2.1s         │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**Features:**

1. **Tab-based filtering:** Reservations / Stop Sales / Unknown
2. **Bulk selection:** Checkbox for each email + Select All
3. **Quick preview:** Parsed data shown inline
4. **Actions per email:**
   - View PDF (modal)
   - Edit parsed data
   - Re-classify
   - Delete
5. **Bulk sync:** "Sync Selected to Sedna" button
6. **Sync history:** Recent sync operations with stats

---

### R3: Sedna Sync Modal (NEW COMPONENT)

**Trigger:** Click "Sync Selected to Sedna" button

**UI Flow:**

```
┌────────────────────────────────────────────────────────────┐
│  Sync to Sedna                                        [X]  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Selected: 15 emails (12 reservations, 3 stop sales)       │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Pre-sync Validation:                                 │  │
│  │  ✅ 12 reservations ready                            │  │
│  │  ✅ 3 stop sales ready                               │  │
│  │  ⚠️ 0 with missing required fields                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  [Cancel]                        [🚀 Start Sync]           │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  Progress: ████████████░░░░░░░░  60% (9/15)                │
│                                                            │
│  Current: Syncing reservation #12345...                    │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Live Results:                                        │  │
│  │  ✅ Reservation #12340 → Sedna ID: RES-2024-5678    │  │
│  │  ✅ Reservation #12341 → Sedna ID: RES-2024-5679    │  │
│  │  ❌ Reservation #12342 → Error: Guest name required │  │
│  │  ✅ Stop Sale #SS-001 → Sedna ID: SS-2024-0123      │  │
│  │  ...                                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

**After Completion:**

```
┌────────────────────────────────────────────────────────────┐
│  Sync Complete ✅                                     [X]  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Summary:                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ✅ Successful:  13                                  │  │
│  │  ❌ Failed:       2                                  │  │
│  │  ⏱️ Duration:    4.2 seconds                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  Failed Items:                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Reservation #12342                                │  │
│  │    Error: Guest name is required                     │  │
│  │    [Retry] [Edit & Retry] [Skip]                     │  │
│  │                                                      │  │
│  │ 2. Reservation #12345                                │  │
│  │    Error: Invalid check-in date format               │  │
│  │    [Retry] [Edit & Retry] [Skip]                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  [📥 Download Report]  [Close]                             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

### R4: Sync Report (DOWNLOADABLE)

**Format:** Excel or PDF

**Excel Structure:**

| Sheet | Columns |
|-------|---------|
| **Summary** | Total, Successful, Failed, Duration, Timestamp |
| **Successful** | Email ID, Type, Subject, Sedna ID, Sync Time |
| **Failed** | Email ID, Type, Subject, Error Message, Error Code |
| **Details** | Full parsed data for all items |

**API Endpoint:**

```yaml
GET /api/sync/report/{sync_id}
Parameters:
  format: excel | pdf
Response:
  Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  Filename: sync-report-{sync_id}-{date}.xlsx
```

---

### R5: Backend API Endpoints (NEW)

```yaml
# Get pending emails with parsed data
GET /api/emails/pending
Query:
  - type: reservation | stopsale | unknown
  - page: 1
  - limit: 50
Response:
  - items: EmailWithParsedData[]
  - total: number
  - page: number

# Bulk sync to Sedna
POST /api/sedna/sync
Body:
  email_ids: number[]
Response:
  sync_id: string
  status: "started"

# Get sync progress (WebSocket or SSE)
GET /api/sedna/sync/{sync_id}/progress
Response (SSE):
  event: progress
  data: { current: 5, total: 15, item: {...}, status: "success" | "failed" }

# Get sync results
GET /api/sedna/sync/{sync_id}/result
Response:
  sync_id: string
  status: "completed" | "partial" | "failed"
  summary:
    total: 15
    successful: 13
    failed: 2
    duration_seconds: 4.2
  successful: SyncResultItem[]
  failed: SyncResultItem[]

# Download sync report
GET /api/sedna/sync/{sync_id}/report
Query:
  format: excel | pdf
Response: File download
```

---

## 🏗️ Implementation Steps

### Phase 1: Backend (4 hours)

1. **Enhance Email Parser** (`parser/service.py`)
   - Improve classification accuracy
   - Extract structured data (guest, dates, hotel, room)
   - PDF text extraction with pdfplumber

2. **Create Sync Service** (`sedna/sync_service.py`)
   - Bulk sync orchestration
   - Progress tracking
   - Error handling per item

3. **Create Sync API** (`routers/sync.py`)
   - POST /api/sedna/sync
   - GET /api/sedna/sync/{id}/progress (SSE)
   - GET /api/sedna/sync/{id}/result
   - GET /api/sedna/sync/{id}/report

4. **Update Database Schema**
   - `sync_runs` table for tracking
   - `sync_items` table for per-item results

### Phase 2: Frontend (4 hours)

1. **Create Processing Page** (`emails/processing/page.tsx`)
   - Tab layout
   - Email cards with parsed data
   - Bulk selection

2. **Create Sync Modal** (`components/SyncModal.tsx`)
   - Pre-sync validation
   - Real-time progress (SSE)
   - Results display

3. **Create Report Download** (`components/SyncReport.tsx`)
   - Download button
   - Format selection

---

## ✅ Success Criteria

### Functional

- [ ] Emails automatically classified as reservation/stopsale/unknown
- [ ] User can view all pending emails in tabbed interface
- [ ] User can select individual or bulk emails
- [ ] Selected emails sync to Sedna API
- [ ] Real-time progress during sync
- [ ] Failed items shown with error messages
- [ ] User can retry failed items
- [ ] Sync report downloadable as Excel

### Performance

- [ ] Email list loads < 2 seconds
- [ ] Sync 100 items < 30 seconds
- [ ] Report generation < 5 seconds

### UX

- [ ] Clear visual feedback during sync
- [ ] Error messages are actionable
- [ ] Mobile-responsive design

---

## 📁 Files to Create/Modify

### Backend (Create)

- [ ] `apps/api/routers/sync.py` - Sync API endpoints
- [ ] `apps/api/sedna/sync_service.py` - Sync orchestration
- [ ] `apps/api/sedna/report_service.py` - Report generation

### Backend (Modify)

- [ ] `apps/api/parser/service.py` - Enhanced classification
- [ ] `apps/api/main.py` - Register sync router

### Frontend (Create)

- [ ] `apps/web/src/app/emails/processing/page.tsx` - Main dashboard
- [ ] `apps/web/src/components/SyncModal.tsx` - Sync dialog
- [ ] `apps/web/src/components/EmailCard.tsx` - Email preview card
- [ ] `apps/web/src/hooks/useSyncProgress.ts` - SSE hook

### Database (Migration)

- [ ] `migrations/002_add_sync_tables.sql`

---

## ⚠️ Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Sedna API rate limits | Implement throttling (5 req/sec) |
| Large PDF attachments | Streaming + temp file cleanup |
| Classification errors | Allow manual re-classification |
| Sync failures | Retry mechanism with exponential backoff |
| Multi-tenant isolation | Tenant ID in all queries |

---

## 🔗 Related Documents

- [x] `2025-12-29-email-fetch-deep-analysis.md` - Email fetch implementation
- [ ] Sedna API Documentation (if available)
- [ ] Juniper Email Format Specification

---

## 📊 Research Questions for Deep Dive

1. **Sedna API:** What are the exact field mappings for reservations and stop sales?
2. **Email Formats:** What variations of Juniper emails exist?
3. **Error Handling:** What are common Sedna API error codes?
4. **PDF Parsing:** What table structures exist in Juniper voucher PDFs?

---

*Priscilla's Optimization Level: Production*
*Estimated Implementation Time: 8-12 hours*
*Confidence: High*
