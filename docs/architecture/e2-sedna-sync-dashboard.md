# Architecture: Sedna Sync Dashboard (E2)

> **Epic:** E2 - Email Processing & Sedna Sync
> **Tarih:** 2025-12-29
> **Durum:** Draft

---

## 1. Tech Stack

### Backend (Existing)

```yaml
Framework: FastAPI 0.109+
Python: 3.11
Database: PostgreSQL 15
ORM: asyncpg (raw SQL)
HTTP Client: httpx (Sedna API calls)
```

### Backend (New)

```yaml
SSE: FastAPI StreamingResponse
Excel: openpyxl
Background Tasks: FastAPI background_tasks
```

### Frontend (Existing)

```yaml
Framework: Next.js 14
React: 18
Language: TypeScript
Styling: Tailwind CSS
Icons: Lucide React
```

### Frontend (New)

```yaml
SSE Client: native EventSource API
State: React useState + custom hooks
```

---

## 2. Source Tree (Updates)

### Backend New Files

```
apps/api/
├── routers/
│   └── sync.py                     # NEW: Sync API endpoints
├── sedna/
│   ├── service.py                  # EXISTING (reuse)
│   ├── routes.py                   # EXISTING (reuse)
│   ├── bulk_sync_service.py        # NEW: Orchestration
│   └── report_service.py           # NEW: Excel generation
├── models/
│   └── sync.py                     # NEW: Sync models
└── main.py                         # MODIFY: Register sync router
```

### Frontend New Files

```
apps/web/src/
├── app/
│   └── emails/
│       └── processing/
│           └── page.tsx            # NEW: Processing dashboard
├── components/
│   ├── SyncModal.tsx               # NEW: Progress dialog
│   ├── SyncResultModal.tsx         # NEW: Results dialog
│   └── EmailProcessingCard.tsx     # NEW: Selectable card
└── hooks/
    └── useSyncProgress.ts          # NEW: SSE hook
```

---

## 3. Database Schema

### Existing Tables (No Changes)

```sql
-- emails table: ✅ Mevcut, değişiklik yok
-- reservations table: ✅ Mevcut, değişiklik yok
-- stop_sales table: ✅ Mevcut, değişiklik yok
-- pipeline_runs table: ✅ Mevcut, değişiklik yok
```

### New Table: sync_runs

```sql
CREATE TABLE IF NOT EXISTS sync_runs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    sync_id VARCHAR(50) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed
    total_items INTEGER DEFAULT 0,
    successful_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sync_runs_tenant ON sync_runs(tenant_id);
CREATE INDEX idx_sync_runs_sync_id ON sync_runs(sync_id);
```

### New Table: sync_items

```sql
CREATE TABLE IF NOT EXISTS sync_items (
    id SERIAL PRIMARY KEY,
    sync_run_id INTEGER NOT NULL REFERENCES sync_runs(id),
    email_id INTEGER NOT NULL REFERENCES emails(id),
    item_type VARCHAR(20) NOT NULL, -- reservation, stop_sale
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, success, failed
    sedna_rec_id INTEGER,
    error_message TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sync_items_run ON sync_items(sync_run_id);
```

---

## 4. API Specification

### POST /api/sync/emails

Start bulk sync for selected emails.

```yaml
Method: POST
Path: /api/sync/emails
Auth: JWT (tenant_id extracted from token)

Request:
  Content-Type: application/json
  Body:
    email_ids: number[]  # List of email IDs to sync

Response (200):
  sync_id: string        # UUID for tracking
  status: "started"
  total_items: number

Response (400):
  detail: "No emails selected"

Response (401):
  detail: "Not authenticated"
```

### GET /api/sync/{sync_id}/progress

Server-Sent Events stream for realtime progress.

```yaml
Method: GET
Path: /api/sync/{sync_id}/progress
Auth: JWT

Response: text/event-stream

Events:
  # Progress event (per item)
  data: {
    "type": "progress",
    "current": 5,
    "total": 15,
    "item": {
      "email_id": 123,
      "type": "reservation",
      "status": "success",
      "sedna_id": "RES-5678"
    }
  }
  
  # Error event (per item)
  data: {
    "type": "progress",
    "current": 6,
    "total": 15,
    "item": {
      "email_id": 124,
      "type": "reservation",
      "status": "failed",
      "error": "Hotel not found in Sedna"
    }
  }
  
  # Complete event (final)
  data: {
    "type": "complete",
    "summary": {
      "total": 15,
      "successful": 13,
      "failed": 2,
      "duration_seconds": 4.2
    }
  }
```

### GET /api/sync/{sync_id}/result

Get final sync results.

```yaml
Method: GET
Path: /api/sync/{sync_id}/result
Auth: JWT

Response (200):
  sync_id: string
  status: "completed" | "partial" | "failed"
  summary:
    total: number
    successful: number
    failed: number
    duration_seconds: number
  successful:
    - email_id: number
      type: string
      sedna_id: string
  failed:
    - email_id: number
      type: string
      error: string
```

### GET /api/sync/{sync_id}/report

Download sync report as Excel.

```yaml
Method: GET
Path: /api/sync/{sync_id}/report
Auth: JWT
Query: format=excel (default)

Response:
  Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  Content-Disposition: attachment; filename="sync-report-{sync_id}.xlsx"
```

### GET /api/emails/pending

Get pending emails with parsed data for selection.

```yaml
Method: GET
Path: /api/emails/pending
Auth: JWT
Query:
  type: reservation | stopsale | unknown (optional)
  status: pending | processed | failed (optional)
  page: number (default: 1)
  limit: number (default: 50)

Response (200):
  items:
    - id: number
      subject: string
      sender: string
      email_type: string
      status: string
      received_at: string
      parsed_data:
        voucher_no: string (if reservation)
        hotel_name: string
        check_in: string (if reservation)
        date_from: string (if stop_sale)
  total: number
  page: number
  pages: number
```

---

## 5. Component Architecture

### Backend Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  routers/sync.py                                            │
│  ├── POST /api/sync/emails     → start_bulk_sync()          │
│  ├── GET  /api/sync/{id}/progress → SSE stream              │
│  ├── GET  /api/sync/{id}/result   → get_sync_result()       │
│  └── GET  /api/sync/{id}/report   → download_report()       │
├─────────────────────────────────────────────────────────────┤
│  sedna/bulk_sync_service.py                                 │
│  ├── start_bulk_sync()          → Create sync_run, return ID│
│  ├── process_sync_items()       → Background processing     │
│  ├── get_sync_progress()        → Generator for SSE         │
│  └── get_sync_result()          → Final result summary      │
├─────────────────────────────────────────────────────────────┤
│  sedna/service.py (EXISTING)                                │
│  ├── sync_reservation()         → Single reservation sync   │
│  └── sync_stop_sale()           → Single stop sale sync     │
├─────────────────────────────────────────────────────────────┤
│  sedna/report_service.py                                    │
│  └── generate_excel_report()    → Create Excel file         │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Components

```
┌─────────────────────────────────────────────────────────────┐
│  /emails/processing/page.tsx                                │
│  ├── State: emails[], selectedIds[], activeTab             │
│  ├── Effect: fetchEmails()                                  │
│  ├── Handlers: handleSelect, handleSelectAll, handleSync    │
│  ├── Render:                                                │
│  │   ├── Stats Cards                                        │
│  │   ├── Tab Navigation                                     │
│  │   ├── Email Card List (with checkboxes)                  │
│  │   └── Sync Button (opens SyncModal)                      │
│  └── Modals:                                                │
│      ├── <SyncModal />                                      │
│      └── <SyncResultModal />                                │
├─────────────────────────────────────────────────────────────┤
│  components/SyncModal.tsx                                   │
│  ├── Props: isOpen, selectedIds, onClose, onComplete        │
│  ├── Hook: useSyncProgress(syncId)                          │
│  └── Render: Progress bar, item status list                 │
├─────────────────────────────────────────────────────────────┤
│  components/SyncResultModal.tsx                             │
│  ├── Props: isOpen, result, onClose, onRetry, onDownload    │
│  └── Render: Summary, failed items, action buttons          │
├─────────────────────────────────────────────────────────────┤
│  hooks/useSyncProgress.ts                                   │
│  ├── Input: syncId                                          │
│  ├── Uses: EventSource                                      │
│  └── Returns: { progress, results, status }                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Coding Standards

### Python

```python
# Async/await kullanımı
async def function_name(param: TypeHint) -> ReturnType:
    """Docstring with description."""
    pass

# Service pattern
class ServiceName:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def method_name(self, tenant_id: int) -> Result:
        async with self.pool.acquire() as conn:
            # DB operations
            pass

# Error handling
try:
    result = await some_operation()
except SomeException as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

### TypeScript

```typescript
// Component pattern
"use client";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function ComponentName({ isOpen, onClose }: Props) {
  const [state, setState] = useState<StateType>(initialValue);
  
  useEffect(() => {
    // Side effects
  }, [dependencies]);
  
  return (
    <div className="...">
      {/* JSX */}
    </div>
  );
}

// Hook pattern
export function useHookName(param: ParamType) {
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    // Effect logic
  }, [param]);
  
  return { data, loading, error };
}
```

---

## 7. Sequence Diagrams

### Bulk Sync Flow

```
Frontend                 Backend                    Sedna API
    │                        │                          │
    │ POST /sync/emails      │                          │
    │ {email_ids: [1,2,3]}   │                          │
    │───────────────────────>│                          │
    │                        │ Create sync_run          │
    │                        │ Start background task    │
    │       {sync_id: "x"}   │                          │
    │<───────────────────────│                          │
    │                        │                          │
    │ GET /sync/x/progress   │                          │
    │ (SSE)                  │                          │
    │───────────────────────>│                          │
    │                        │ For each email:          │
    │                        │   Get reservation/SS     │
    │                        │──────────────────────────>
    │                        │                          │ POST /InsertReservation
    │                        │<──────────────────────────
    │       SSE: progress    │                          │
    │<───────────────────────│                          │
    │                        │   (repeat for each)      │
    │                        │                          │
    │       SSE: complete    │                          │
    │<───────────────────────│                          │
    │                        │                          │
    │ GET /sync/x/report     │                          │
    │───────────────────────>│                          │
    │       Excel file       │                          │
    │<───────────────────────│                          │
    │                        │                          │
```

---

## 8. Security Considerations

### Authentication

```yaml
All endpoints:
  - Require valid JWT token
  - Extract tenant_id from token
  - Filter all queries by tenant_id
```

### Multi-Tenant Isolation

```sql
-- All queries MUST include tenant_id filter
SELECT * FROM emails WHERE tenant_id = $1 AND id = $2;
SELECT * FROM sync_runs WHERE tenant_id = $1 AND sync_id = $2;
```

### Rate Limiting

```yaml
Sedna API calls:
  - Max 5 requests/second
  - Implement asyncio.sleep(0.2) between calls
  - Retry with exponential backoff (3 attempts)
```

---

## 9. Deployment Notes

### Database Migration

```bash
# Run migration for new tables
kubectl exec -it pod/entegrasyon-api -- python -c "
import asyncio
import asyncpg
import os

async def migrate():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_runs (...)
    ''')
    
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_items (...)
    ''')
    
    await conn.close()

asyncio.run(migrate())
"
```

### Docker Build

```bash
# Update Docker image
docker buildx build --platform linux/amd64 \
  -t ghcr.io/ayavuzer/entegrasyon-api:v1.4.0-sync-dashboard \
  --push .
```

### Kubernetes Deploy

```bash
kubectl set image deployment/entegrasyon-api \
  api=ghcr.io/ayavuzer/entegrasyon-api:v1.4.0-sync-dashboard \
  -n entegrasyon
```

---

## 10. Testing Strategy

### Backend Tests

```python
# tests/test_sync.py

@pytest.mark.asyncio
async def test_start_bulk_sync():
    """Test bulk sync initiation."""
    response = await client.post("/api/sync/emails", json={"email_ids": [1, 2, 3]})
    assert response.status_code == 200
    assert "sync_id" in response.json()

@pytest.mark.asyncio
async def test_sync_progress_sse():
    """Test SSE progress stream."""
    # Start sync first
    # Connect to SSE
    # Verify events received

@pytest.mark.asyncio
async def test_sync_report_download():
    """Test Excel report generation."""
    response = await client.get(f"/api/sync/{sync_id}/report")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
```

### Frontend Tests

```typescript
// __tests__/SyncModal.test.tsx

describe("SyncModal", () => {
  it("shows progress when sync starts", async () => {
    render(<SyncModal isOpen selectedIds={[1, 2, 3]} />);
    expect(screen.getByText(/0%/)).toBeInTheDocument();
  });
  
  it("updates on SSE events", async () => {
    // Mock EventSource
    // Fire events
    // Check UI updates
  });
});
```

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-29 | 1.0 | Initial architecture draft |

---

*Architecture Owner: Engineering Team*
*Review Status: Pending*
