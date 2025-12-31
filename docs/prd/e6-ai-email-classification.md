# E6: AI Email Classification & Extraction

> **Epic ID:** E6
> **Priority:** P0 (High Value)
> **Estimated SP:** 8
> **Status:** Ready for Development
> **Created:** 2025-12-29

---

## 📋 Epic Summary

Farklı otellerden gelen çeşitli formatlardaki e-mailleri AI ile sınıflandır ve parse et. Gemini 2.5 Flash + Pydantic kullanarak stop sale ve rezervasyon verilerini %95+ accuracy ile çıkar.

---

## 🎯 Goals

1. Email'leri AI ile sınıflandır: stop_sale / reservation / other
2. Stop sale email'lerinden structured data çıkar
3. Rezervasyon email/PDF'lerinden structured data çıkar
4. Mevcut regex parser'ı AI ile değiştir/tamamla
5. Çok dilli destek: TR, EN, RU, UK, DE

---

## 📊 Background & Context

### Problem Statement

Mevcut regex-based parser:

- ~70% accuracy
- Her yeni format için kod değişikliği gerekli
- Çok dilli destek için karmaşık pattern'ler
- Bakım maliyeti yüksek

### AI Çözümü (Research Sonucu)

| Kriter | Regex | AI (Gemini) |
|--------|-------|-------------|
| Accuracy | ~70% | ~95%+ |
| Yeni Format | Kod değişikliği | Otomatik |
| Çok Dil | Zor | Native |
| Maliyet | $0 | ~$0.0001/email |
| Bakım | Yüksek | Düşük |

### Research Reference

`.agent/artifacts/research/2025-12-29-ai-email-classification-parsing-deep-research.md`

---

## 🔧 Technical Approach

### Teknoloji Seçimi

| Component | Seçim | Neden |
|-----------|-------|-------|
| LLM | Google Gemini 2.5 Flash | Düşük maliyet, yüksek hız, Türkçe |
| Schema | Pydantic v2 | Type-safe, validation |
| SDK | google-genai | Official Python SDK |
| Fallback | Mevcut regex parser | AI failure durumu |

### Data Flow

```
Email → Classification → Extraction → Validation → Database → Sedna Sync
```

---

## 📝 Stories

### E6.S1: Gemini AI Service Setup

**Story ID:** E6.S1
**SP:** 2
**Priority:** P0
**Type:** Foundation

**Description:**
Gemini API entegrasyonu için temel service'leri oluştur.

**Acceptance Criteria:**

- [ ] `apps/api/ai/` modülü oluştur
- [ ] Pydantic models tanımla (EmailClassification, StopSaleExtraction, ReservationExtraction)
- [ ] Gemini client wrapper implement et
- [ ] API key tenant_settings'ten al
- [ ] requirements.txt'e google-genai ekle

**Technical Notes:**

```python
# apps/api/ai/models.py
class EmailClassification(BaseModel):
    email_type: Literal["stop_sale", "reservation", "other"]
    confidence: float
    language: str

class StopSaleExtraction(BaseModel):
    hotel_name: str
    date_from: date
    date_to: date
    room_types: list[str] = []
    is_close: bool = True
```

**Files to Create:**

- `apps/api/ai/__init__.py`
- `apps/api/ai/models.py`
- `apps/api/ai/client.py`
- `apps/api/ai/prompts.py`

---

### E6.S2: Email Classification Service

**Story ID:** E6.S2
**SP:** 2
**Priority:** P0
**Type:** Feature

**Description:**
Email'leri AI ile sınıflandır: stop_sale, reservation, other.

**Acceptance Criteria:**

- [ ] `EmailClassifier` service oluştur
- [ ] Subject + body'den classification yap
- [ ] Confidence score döndür (threshold: 0.85)
- [ ] Düşük confidence'da fallback'e geç
- [ ] Dil tespiti yap (tr, en, ru, uk, de)

**System Prompt:**

```
Analyze this email and classify it as:
- stop_sale: Hotel announcing rooms are closed for sale
- reservation: Booking confirmation or voucher
- other: Any other email type

Return JSON with: email_type, confidence, language
```

---

### E6.S3: Stop Sale Extraction Service

**Story ID:** E6.S3
**SP:** 2
**Priority:** P0
**Type:** Feature

**Description:**
Stop sale email'lerinden structured data çıkar.

**Acceptance Criteria:**

- [ ] `StopSaleExtractor` service oluştur
- [ ] Hotel name, dates, room types çıkar
- [ ] Farklı formatları handle et
- [ ] Çok dilli email'leri destekle (TR, EN, RU)
- [ ] Extraction confidence score döndür

**Fields to Extract:**

```python
StopSaleExtraction(
    hotel_name: str,
    date_from: date,
    date_to: date,
    room_types: list[str] = [],  # empty = all
    board_types: list[str] = [],
    is_close: bool = True,
    reason: Optional[str] = None,
)
```

---

### E6.S4: Parser Integration

**Story ID:** E6.S4
**SP:** 2
**Priority:** P1
**Type:** Integration

**Description:**
AI extraction'ı mevcut EmailParserService'e entegre et.

**Acceptance Criteria:**

- [ ] AI parser'ı primary olarak kullan
- [ ] Regex parser'ı fallback olarak tut
- [ ] Confidence < 0.85 ise fallback'e geç
- [ ] AI failure durumunda otomatik fallback
- [ ] Logging ve metrics ekle

**Integration Pattern:**

```python
async def parse_email(self, email_id, tenant_id):
    # Try AI first
    if ai_enabled and gemini_api_key:
        result = await self.ai_parser.parse(email)
        if result.confidence >= 0.85:
            return result
    
    # Fallback to regex
    return await self.regex_parser.parse(email)
```

---

## 📊 Story Points Summary

| Story | SP | Priority | Type |
|-------|:--:|----------|------|
| E6.S1 | 2 | P0 | Foundation |
| E6.S2 | 2 | P0 | Feature |
| E6.S3 | 2 | P0 | Feature |
| E6.S4 | 2 | P1 | Integration |
| **Total** | **8** | | |

---

## 🔗 Dependencies

- E5 (Auth Fix) - ✅ Completed
- E4 (Hotel Fuzzy Match) - ✅ Completed
- Gemini API Key - Required

---

## 📐 Technical Requirements

### API Key Management

```sql
-- tenant_settings'e ekle
ALTER TABLE tenant_settings 
ADD COLUMN gemini_api_key_encrypted TEXT;
```

### Environment Variables

```bash
# Default API key (fallback)
GEMINI_API_KEY=xxx

# Per-tenant override in tenant_settings
```

### Dependencies

```
# requirements.txt
google-genai>=0.5.0
pydantic>=2.0
```

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Rate Limit | Sync yavaşlar | Batch processing |
| AI Hallucination | Yanlış data | Validation + low temperature |
| Gemini Down | Parse fails | Regex fallback |
| Maliyet | Beklenenden yüksek | Usage monitoring |

---

## 📚 References

- Research: `.agent/artifacts/research/2025-12-29-ai-email-classification-parsing-deep-research.md`
- Gemini API: <https://ai.google.dev/gemini-api/docs>
- Pydantic AI: <https://ai.pydantic.dev/>

---

*Epic created: 2025-12-29*
