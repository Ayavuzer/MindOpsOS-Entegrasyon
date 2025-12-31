# E6 AI Email Parsing - Frontend Integration Analysis

**Tarih:** 2025-12-31  
**Proje:** MindOpsOS-Entegrasyon  
**Modül:** Frontend (Next.js 14)  
**Backend Version:** v1.9.1-e6-ai-parsing  

---

## 1. Executive Summary

E6 Epic ile backend'e eklenen AI-powered email parsing özelliklerinin frontend'e entegrasyonu için kapsamlı analiz raporu. Bu rapor, mevcut frontend yapısını analiz eder, yeni endpoint'leri nasıl kullanabileceğimizi belirler ve implementasyon önerileri sunar.

---

## 2. Mevcut Frontend Yapısı

### 2.1 Teknoloji Stack

| Teknoloji | Versiyon |
|-----------|----------|
| Next.js | 14.x |
| React | 18.x |
| TypeScript | 5.x |
| Tailwind CSS | - (inline styles kullanılıyor) |
| Icons | Lucide React |

### 2.2 Sayfa Yapısı

```
apps/web/src/app/
├── emails/              # Email listesi
├── history/             # İşlem geçmişi
├── login/               # Giriş
├── register/            # Kayıt
├── reservations/        # Rezervasyonlar
├── settings/            # Ayarlar (Email konfigürasyonu)
├── stop-sales/          # Stop Sale listesi ⭐
├── layout.tsx
└── page.tsx             # Dashboard
```

### 2.3 Mevcut Komponentler

| Komponent | Dosya | İşlev |
|-----------|-------|-------|
| `EmailAuthSelector` | `components/EmailAuthSelector.tsx` | OAuth/Password auth seçimi |
| `EmailSetupGuide` | `components/EmailSetupGuide.tsx` | OAuth setup kılavuzu |
| `StopSalesPage` | `app/stop-sales/page.tsx` | Stop sale listesi |

---

## 3. Yeni Backend Endpoint'leri

### 3.1 AI Status Endpoint

```typescript
// GET /ai/status
interface AIStatusResponse {
    available: boolean;
    model: string | null;
}
```

### 3.2 Email Classification Endpoint

```typescript
// POST /ai/classify
interface ClassifyRequest {
    subject: string;
    body: string;
}

interface ClassifyResponse {
    success: boolean;
    email_type: "stop_sale" | "reservation" | "other";
    confidence: number;  // 0.0 - 1.0
    language: string;    // "tr", "en", "ru", "de", "uk"
    reasoning: string;
    used_ai: boolean;
    fallback_reason: string | null;
}
```

### 3.3 Stop Sale Extraction Endpoint

```typescript
// POST /ai/extract-stop-sale
interface ExtractStopSaleRequest {
    subject: string;
    body: string;
    email_date?: string;  // ISO format
}

interface ExtractStopSaleResponse {
    success: boolean;
    hotel_name: string | null;
    date_from: string | null;  // YYYY-MM-DD
    date_to: string | null;    // YYYY-MM-DD
    room_types: string[];
    is_close: boolean;
    reason: string | null;
    confidence: number;
    error: string | null;
}
```

---

## 4. Frontend Entegrasyon Önerileri

### 4.1 AI Status Indicator (Header Badge)

**Konum:** Dashboard veya Header

**Tasarım:**

```tsx
// components/AIStatusBadge.tsx
"use client";

import { useState, useEffect } from "react";
import { Brain, CheckCircle, XCircle, Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export function AIStatusBadge() {
    const [status, setStatus] = useState<{available: boolean; model: string | null} | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${API_URL}/ai/status`)
            .then(res => res.json())
            .then(data => {
                setStatus(data);
                setLoading(false);
            })
            .catch(() => {
                setStatus({ available: false, model: null });
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-full">
                <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                <span className="text-xs text-slate-400">AI Loading...</span>
            </div>
        );
    }

    return (
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${
            status?.available 
                ? "bg-emerald-500/10 border border-emerald-500/30" 
                : "bg-red-500/10 border border-red-500/30"
        }`}>
            <Brain className={`w-4 h-4 ${status?.available ? "text-emerald-400" : "text-red-400"}`} />
            {status?.available ? (
                <span className="text-xs text-emerald-400">AI Active: {status.model}</span>
            ) : (
                <span className="text-xs text-red-400">AI Offline</span>
            )}
        </div>
    );
}
```

---

### 4.2 Stop Sales Page Enhancement

**Mevcut Özellikler:**

- Stop sale listesi görüntüleme
- Filtreleme (Close/Open)
- Sedna sync durumu

**Önerilen Yeni Özellikler:**

1. **AI Confidence Badge**
2. **Parse Method Indicator (AI vs Regex)**
3. **Manual Re-parse Button**

**Güncellenmiş Interface:**

```typescript
interface StopSale {
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
    // YENİ ALANLAR (Backend desteği gerekli)
    ai_parsed?: boolean;        // AI ile mi parse edildi?
    ai_confidence?: number;     // AI confidence score (0-1)
    parse_method?: "ai" | "regex" | "manual";
}
```

**Confidence Badge Komponenti:**

```tsx
// components/ConfidenceBadge.tsx
interface ConfidenceBadgeProps {
    confidence: number;
    isAI: boolean;
}

export function ConfidenceBadge({ confidence, isAI }: ConfidenceBadgeProps) {
    const percentage = Math.round(confidence * 100);
    
    let colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    if (percentage < 70) {
        colorClass = "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
    }
    if (percentage < 50) {
        colorClass = "bg-red-500/10 text-red-400 border-red-500/30";
    }

    return (
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs border ${colorClass}`}>
            {isAI ? (
                <Brain className="w-3 h-3" />
            ) : (
                <Code className="w-3 h-3" />
            )}
            <span>{isAI ? "AI" : "Regex"}: {percentage}%</span>
        </div>
    );
}
```

---

### 4.3 Email Preview with AI Analysis

**Konum:** Email detay sayfası veya modal

**Özellikler:**

- Email içeriği görüntüleme
- AI ile classification yapma
- Extraction sonuçlarını preview
- Manual düzeltme imkanı

```tsx
// components/EmailAIPreview.tsx
"use client";

import { useState } from "react";
import { Brain, Loader2, RefreshCw, CheckCircle, AlertTriangle } from "lucide-react";

interface EmailAIPreviewProps {
    email: {
        id: number;
        subject: string;
        body_text: string;
        received_at: string;
    };
    onApplyExtraction: (extraction: ExtractStopSaleResponse) => void;
}

export function EmailAIPreview({ email, onApplyExtraction }: EmailAIPreviewProps) {
    const [classifying, setClassifying] = useState(false);
    const [extracting, setExtracting] = useState(false);
    const [classification, setClassification] = useState<ClassifyResponse | null>(null);
    const [extraction, setExtraction] = useState<ExtractStopSaleResponse | null>(null);

    const handleClassify = async () => {
        setClassifying(true);
        try {
            const res = await fetch(`${API_URL}/ai/classify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: email.subject,
                    body: email.body_text,
                }),
            });
            const data = await res.json();
            setClassification(data);
        } finally {
            setClassifying(false);
        }
    };

    const handleExtract = async () => {
        setExtracting(true);
        try {
            const res = await fetch(`${API_URL}/ai/extract-stop-sale`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: email.subject,
                    body: email.body_text,
                    email_date: email.received_at,
                }),
            });
            const data = await res.json();
            setExtraction(data);
        } finally {
            setExtracting(false);
        }
    };

    return (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
            {/* Email Content */}
            <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white">{email.subject}</h3>
                <p className="text-sm text-slate-400 whitespace-pre-line line-clamp-6">
                    {email.body_text}
                </p>
            </div>

            {/* AI Actions */}
            <div className="flex gap-2 pt-4 border-t border-slate-800">
                <button
                    onClick={handleClassify}
                    disabled={classifying}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition disabled:opacity-50"
                >
                    {classifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
                    Classify
                </button>

                <button
                    onClick={handleExtract}
                    disabled={extracting}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
                >
                    {extracting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    Extract Stop Sale
                </button>
            </div>

            {/* Classification Result */}
            {classification && (
                <div className="p-4 bg-slate-800/50 rounded-lg space-y-2">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-300">Classification:</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            classification.email_type === "stop_sale" 
                                ? "bg-red-500/20 text-red-400" 
                                : classification.email_type === "reservation"
                                    ? "bg-blue-500/20 text-blue-400"
                                    : "bg-slate-500/20 text-slate-400"
                        }`}>
                            {classification.email_type.toUpperCase()}
                        </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span>Confidence: {Math.round(classification.confidence * 100)}%</span>
                        <span>Language: {classification.language.toUpperCase()}</span>
                        <span>{classification.used_ai ? "AI" : "Regex"}</span>
                    </div>
                </div>
            )}

            {/* Extraction Result */}
            {extraction && extraction.success && (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-emerald-400">Extraction Result</span>
                        <span className="text-xs text-emerald-400/70">
                            Confidence: {Math.round(extraction.confidence * 100)}%
                        </span>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                            <span className="text-slate-400">Hotel:</span>
                            <span className="ml-2 text-white">{extraction.hotel_name}</span>
                        </div>
                        <div>
                            <span className="text-slate-400">Type:</span>
                            <span className={`ml-2 ${extraction.is_close ? "text-red-400" : "text-emerald-400"}`}>
                                {extraction.is_close ? "Close" : "Open"}
                            </span>
                        </div>
                        <div>
                            <span className="text-slate-400">From:</span>
                            <span className="ml-2 text-white">{extraction.date_from}</span>
                        </div>
                        <div>
                            <span className="text-slate-400">To:</span>
                            <span className="ml-2 text-white">{extraction.date_to}</span>
                        </div>
                        {extraction.room_types.length > 0 && (
                            <div className="col-span-2">
                                <span className="text-slate-400">Rooms:</span>
                                <span className="ml-2 text-white">{extraction.room_types.join(", ")}</span>
                            </div>
                        )}
                        {extraction.reason && (
                            <div className="col-span-2">
                                <span className="text-slate-400">Reason:</span>
                                <span className="ml-2 text-white">{extraction.reason}</span>
                            </div>
                        )}
                    </div>

                    <button
                        onClick={() => onApplyExtraction(extraction)}
                        className="w-full mt-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition flex items-center justify-center gap-2"
                    >
                        <CheckCircle className="w-4 h-4" />
                        Apply Extraction
                    </button>
                </div>
            )}

            {/* Extraction Error */}
            {extraction && !extraction.success && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <div className="flex items-center gap-2 text-red-400">
                        <AlertTriangle className="w-4 h-4" />
                        <span className="text-sm">{extraction.error}</span>
                    </div>
                </div>
            )}
        </div>
    );
}
```

---

### 4.4 AI Settings Panel

**Konum:** Settings sayfası altında yeni sekme

```tsx
// app/settings/ai/page.tsx
export default function AISettingsPage() {
    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-white">AI Settings</h2>
            
            {/* AI Status Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">AI Service Status</h3>
                <AIStatusCard />
            </div>

            {/* Confidence Threshold */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Confidence Threshold</h3>
                <p className="text-sm text-slate-400 mb-4">
                    AI extraction sonuçları bu threshold altındaysa regex fallback kullanılır.
                </p>
                <div className="flex items-center gap-4">
                    <input
                        type="range"
                        min="0"
                        max="100"
                        defaultValue="85"
                        className="w-48"
                    />
                    <span className="text-white font-mono">85%</span>
                </div>
            </div>

            {/* AI Model Info */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Model Information</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span className="text-slate-400">Model:</span>
                        <span className="ml-2 text-white">Gemini 2.0 Flash</span>
                    </div>
                    <div>
                        <span className="text-slate-400">Provider:</span>
                        <span className="ml-2 text-white">Google AI</span>
                    </div>
                    <div>
                        <span className="text-slate-400">Languages:</span>
                        <span className="ml-2 text-white">TR, EN, RU, DE, UK</span>
                    </div>
                    <div>
                        <span className="text-slate-400">Fallback:</span>
                        <span className="ml-2 text-white">Regex Parser</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
```

---

## 5. Backend Değişiklik Gereksinimleri

Frontend entegrasyonu için backend'de aşağıdaki değişiklikler önerilir:

### 5.1 Database Schema Updates

```sql
-- stop_sales tablosuna AI metadata ekle
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS ai_parsed BOOLEAN DEFAULT FALSE;
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS ai_confidence DECIMAL(3,2) DEFAULT NULL;
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS parse_method VARCHAR(20) DEFAULT 'regex';
```

### 5.2 API Response Updates

Mevcut `/api/stop-sales` endpoint'ine AI alanları ekle:

```python
# apps/api/routers/stop_sales.py
@router.get("")
async def list_stop_sales(...):
    # ... existing code ...
    
    # Add AI metadata to response
    return [
        {
            **stop_sale.dict(),
            "ai_parsed": stop_sale.ai_parsed,
            "ai_confidence": stop_sale.ai_confidence,
            "parse_method": stop_sale.parse_method,
        }
        for stop_sale in stop_sales
    ]
```

---

## 6. Implementasyon Planı

### Phase 1: Core Integration (2 SP)

| Task | Dosya | Öncelik |
|------|-------|---------|
| AI Status Badge | `components/AIStatusBadge.tsx` | P0 |
| TypeScript interfaces | `types/ai.ts` | P0 |
| API client functions | `lib/api/ai.ts` | P0 |

### Phase 2: Stop Sales Enhancement (2 SP)

| Task | Dosya | Öncelik |
|------|-------|---------|
| Confidence Badge | `components/ConfidenceBadge.tsx` | P1 |
| Stop Sales page update | `app/stop-sales/page.tsx` | P1 |
| DB schema migration | Backend | P1 |

### Phase 3: Email AI Preview (3 SP)

| Task | Dosya | Öncelik |
|------|-------|---------|
| Email AI Preview modal | `components/EmailAIPreview.tsx` | P2 |
| Manual re-parse button | `app/emails/page.tsx` | P2 |
| AI Settings page | `app/settings/ai/page.tsx` | P2 |

---

## 7. Success Criteria

### Functional

- [ ] AI status badge dashboard'da görünür
- [ ] Stop sales listesinde AI/Regex indicator
- [ ] Email preview'da AI extraction çalışır
- [ ] Confidence score doğru gösterilir

### Performance

- [ ] AI status check < 500ms
- [ ] Classification < 2s
- [ ] Extraction < 3s

### UX

- [ ] Loading states tüm AI operasyonlarında
- [ ] Error handling ve user feedback
- [ ] Mobile responsive design

---

## 8. Risk ve Mitigasyonlar

| Risk | Etki | Mitigasyon |
|------|------|------------|
| AI service down | High | Fallback to regex, status indicator |
| Slow response | Medium | Loading states, timeout handling |
| Low confidence | Low | Clear UI feedback, manual override |

---

## 9. Dosya Listesi

### Yeni Dosyalar

```
apps/web/src/
├── components/
│   ├── AIStatusBadge.tsx       ⭐ NEW
│   ├── ConfidenceBadge.tsx     ⭐ NEW
│   └── EmailAIPreview.tsx      ⭐ NEW
├── types/
│   └── ai.ts                   ⭐ NEW
├── lib/
│   └── api/
│       └── ai.ts               ⭐ NEW
└── app/
    └── settings/
        └── ai/
            └── page.tsx        ⭐ NEW
```

### Güncellenecek Dosyalar

```
apps/web/src/
├── app/
│   ├── page.tsx               📝 Add AI badge
│   ├── stop-sales/
│   │   └── page.tsx           📝 Add confidence display
│   └── emails/
│       └── page.tsx           📝 Add AI preview button
└── components/
    └── Header.tsx             📝 Add AI badge (if exists)
```

---

**Hazırlayan:** Antigravity Agent  
**Tarih:** 2025-12-31  
**Versiyon:** 1.0
