# E7: AI Frontend Integration - Architecture

## 1. Overview

E7 Epic, E6 backend AI özelliklerini frontend'e entegre eder. Bu doküman teknik implementasyon detaylarını içerir.

---

## 2. Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | Next.js | 14.x |
| UI Library | React | 18.x |
| Language | TypeScript | 5.x |
| Styling | Tailwind-style inline | Custom |
| Icons | Lucide React | Latest |
| State | React Hooks | Built-in |
| HTTP Client | Fetch API | Native |

---

## 3. Directory Structure

```
apps/web/src/
├── app/
│   ├── settings/
│   │   └── ai/
│   │       └── page.tsx        # E7.S4: AI Settings page
│   ├── stop-sales/
│   │   └── page.tsx            # E7.S2: Updated with confidence
│   ├── emails/
│   │   └── page.tsx            # E7.S3: AI Preview integration
│   └── page.tsx                # E7.S1: AI Status badge
├── components/
│   ├── ai/
│   │   ├── AIStatusBadge.tsx   # E7.S1: Status indicator
│   │   ├── ConfidenceBadge.tsx # E7.S2: Confidence display
│   │   └── EmailAIPreview.tsx  # E7.S3: Preview modal
│   └── ui/
│       └── Modal.tsx           # Reusable modal (if needed)
├── lib/
│   └── api/
│       └── ai.ts               # AI API client functions
└── types/
    └── ai.ts                   # TypeScript interfaces
```

---

## 4. TypeScript Interfaces

### 4.1 Core Types (`types/ai.ts`)

```typescript
// AI Service Status
export interface AIStatus {
    available: boolean;
    model: string | null;
}

// Email Classification
export interface ClassifyRequest {
    subject: string;
    body: string;
}

export interface ClassifyResponse {
    success: boolean;
    email_type: "stop_sale" | "reservation" | "other";
    confidence: number;
    language: string;
    reasoning: string;
    used_ai: boolean;
    fallback_reason: string | null;
}

// Stop Sale Extraction
export interface ExtractStopSaleRequest {
    subject: string;
    body: string;
    email_date?: string;
}

export interface ExtractStopSaleResponse {
    success: boolean;
    hotel_name: string | null;
    date_from: string | null;
    date_to: string | null;
    room_types: string[];
    is_close: boolean;
    reason: string | null;
    confidence: number;
    error: string | null;
}

// Extended StopSale type
export interface StopSale {
    id: number;
    hotel_name: string;
    date_from: string;
    date_to: string;
    room_types: string[];
    board_types: string[];
    is_close: boolean;
    reason: string;
    sedna_synced: boolean;
    created_at: string;
    // AI metadata (E7.S2)
    ai_parsed?: boolean;
    ai_confidence?: number;
    parse_method?: "ai" | "regex" | "manual";
}
```

---

## 5. API Client (`lib/api/ai.ts`)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export async function getAIStatus(): Promise<AIStatus> {
    const res = await fetch(`${API_URL}/ai/status`);
    if (!res.ok) {
        return { available: false, model: null };
    }
    return res.json();
}

export async function classifyEmail(
    request: ClassifyRequest
): Promise<ClassifyResponse> {
    const res = await fetch(`${API_URL}/ai/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    return res.json();
}

export async function extractStopSale(
    request: ExtractStopSaleRequest
): Promise<ExtractStopSaleResponse> {
    const res = await fetch(`${API_URL}/ai/extract-stop-sale`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    return res.json();
}

export async function reparseStopSale(
    stopSaleId: number,
    token: string
): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_URL}/api/stop-sales/${stopSaleId}/reparse`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
        },
    });
    return res.json();
}
```

---

## 6. Component Specifications

### 6.1 AIStatusBadge (`components/ai/AIStatusBadge.tsx`)

**Purpose:** Display AI service status in header/dashboard

**Props:** None (self-contained)

**State:**

```typescript
const [status, setStatus] = useState<AIStatus | null>(null);
const [loading, setLoading] = useState(true);
```

**Render Logic:**

```
if loading → Loader2 icon + "AI Loading..."
if !available → Red badge + "AI Offline"
if available → Green badge + "AI Active: {model}"
```

**Caching:** Store in localStorage for 5 minutes

```typescript
const CACHE_KEY = "ai_status_cache";
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
```

---

### 6.2 ConfidenceBadge (`components/ai/ConfidenceBadge.tsx`)

**Purpose:** Show AI/Regex confidence for stop sales

**Props:**

```typescript
interface ConfidenceBadgeProps {
    confidence: number;      // 0.0 - 1.0
    isAI: boolean;           // AI or Regex
    showLabel?: boolean;     // Show text label
}
```

**Color Logic:**

```typescript
const getColorClass = (percentage: number) => {
    if (percentage >= 70) return "bg-emerald-500/10 text-emerald-400";
    if (percentage >= 50) return "bg-yellow-500/10 text-yellow-400";
    return "bg-red-500/10 text-red-400";
};
```

**Icon:**

- AI: `<Brain />` icon
- Regex: `<Code />` icon

---

### 6.3 EmailAIPreview (`components/ai/EmailAIPreview.tsx`)

**Purpose:** Preview and apply AI extraction results

**Props:**

```typescript
interface EmailAIPreviewProps {
    email: {
        id: number;
        subject: string;
        body_text: string;
        received_at: string;
    };
    onApply: (extraction: ExtractStopSaleResponse) => void;
    onClose: () => void;
}
```

**State:**

```typescript
const [classifying, setClassifying] = useState(false);
const [extracting, setExtracting] = useState(false);
const [classification, setClassification] = useState<ClassifyResponse | null>(null);
const [extraction, setExtraction] = useState<ExtractStopSaleResponse | null>(null);
```

**UI Sections:**

1. Email content (subject + body preview)
2. Action buttons (Classify, Extract)
3. Classification result panel
4. Extraction result panel with Apply button
5. Error display

---

## 7. Database Changes

### 7.1 Migration SQL

```sql
-- File: apps/api/migrations/20251231_e7_ai_frontend.sql

-- Add AI metadata columns to stop_sales
ALTER TABLE stop_sales 
    ADD COLUMN IF NOT EXISTS ai_parsed BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS ai_confidence DECIMAL(3,2) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS parse_method VARCHAR(20) DEFAULT 'regex';

-- Update existing records
UPDATE stop_sales 
SET parse_method = 'regex', ai_parsed = FALSE 
WHERE parse_method IS NULL;

-- Index for filtering
CREATE INDEX IF NOT EXISTS idx_stop_sales_ai_parsed 
ON stop_sales(ai_parsed);
```

### 7.2 Backend Model Update

```python
# apps/api/models/stop_sale.py (update)
class StopSale(Base):
    # ... existing fields ...
    
    # AI metadata
    ai_parsed = Column(Boolean, default=False)
    ai_confidence = Column(Numeric(3, 2), nullable=True)
    parse_method = Column(String(20), default="regex")
```

---

## 8. Data Flow

### 8.1 AI Status Flow

```
[Dashboard Load]
      │
      ▼
[Check localStorage cache]
      │
      ├── Cache valid → Display cached status
      │
      └── Cache expired/missing
              │
              ▼
        [GET /ai/status]
              │
              ▼
        [Update cache + display]
```

### 8.2 Stop Sale List Flow

```
[Stop Sales Page Load]
      │
      ▼
[GET /api/stop-sales]
      │
      ▼
[Response includes ai_parsed, ai_confidence]
      │
      ▼
[Render ConfidenceBadge for each]
```

### 8.3 Email AI Preview Flow

```
[User clicks "AI Preview" on email]
      │
      ▼
[Open EmailAIPreview modal]
      │
      ├── [Click Classify] → POST /ai/classify → Show result
      │
      └── [Click Extract] → POST /ai/extract-stop-sale → Show result
              │
              ▼
        [Click Apply] → Save to stop_sales → Close modal
```

---

## 9. Error Handling

### 9.1 Network Errors

```typescript
try {
    const data = await getAIStatus();
    setStatus(data);
} catch (error) {
    // Network failure - show offline status
    setStatus({ available: false, model: null });
    console.error("AI Status check failed:", error);
}
```

### 9.2 Timeout Handling

```typescript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

try {
    const res = await fetch(url, { signal: controller.signal });
    // ...
} finally {
    clearTimeout(timeoutId);
}
```

### 9.3 User Feedback

| State | Display |
|-------|---------|
| Loading | Spinner + "Processing..." |
| Success | Green checkmark + result |
| Error | Red alert + error message |
| Timeout | Yellow warning + "Request timed out" |

---

## 10. Accessibility

### 10.1 ARIA Labels

```tsx
<button
    aria-label="Check AI service status"
    aria-busy={loading}
>
    {loading ? <Loader2 className="animate-spin" /> : <Brain />}
</button>
```

### 10.2 Color Contrast

| Element | Background | Text | Ratio |
|---------|------------|------|-------|
| Success badge | #10b981/10 | #10b981 | 4.5:1+ |
| Warning badge | #f59e0b/10 | #f59e0b | 4.5:1+ |
| Error badge | #ef4444/10 | #ef4444 | 4.5:1+ |

---

## 11. Testing Strategy

### 11.1 Unit Tests

```typescript
// __tests__/components/AIStatusBadge.test.tsx
describe("AIStatusBadge", () => {
    it("shows loading state initially", () => {
        render(<AIStatusBadge />);
        expect(screen.getByText("AI Loading...")).toBeInTheDocument();
    });

    it("shows active when available", async () => {
        mockFetch({ available: true, model: "gemini-2.0-flash" });
        render(<AIStatusBadge />);
        await waitFor(() => {
            expect(screen.getByText(/AI Active/)).toBeInTheDocument();
        });
    });

    it("shows offline when unavailable", async () => {
        mockFetch({ available: false, model: null });
        render(<AIStatusBadge />);
        await waitFor(() => {
            expect(screen.getByText("AI Offline")).toBeInTheDocument();
        });
    });
});
```

### 11.2 Integration Tests

- Test AI status → Stop sales page flow
- Test Email preview → Extraction → Apply flow
- Test error recovery scenarios

---

## 12. Performance Considerations

### 12.1 Caching Strategy

| Data | Cache Location | TTL |
|------|----------------|-----|
| AI Status | localStorage | 5 min |
| Classification | No cache | - |
| Extraction | No cache | - |

### 12.2 Bundle Size Impact

| Component | Est. Size |
|-----------|-----------|
| AIStatusBadge | ~2KB |
| ConfidenceBadge | ~1KB |
| EmailAIPreview | ~5KB |
| API lib | ~1KB |
| Types | ~0.5KB |
| **Total** | **~10KB** |

---

## 13. Deployment Notes

### 13.1 Environment Variables

```env
NEXT_PUBLIC_API_URL=https://entegrasyon.mindops.net
```

### 13.2 Feature Flags (Optional)

```typescript
const AI_FEATURES_ENABLED = process.env.NEXT_PUBLIC_AI_FEATURES === "true";
```

---

**Created:** 2025-12-31  
**Author:** Antigravity Agent  
**Version:** 1.0
