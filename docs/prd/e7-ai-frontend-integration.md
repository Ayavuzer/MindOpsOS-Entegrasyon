# E7: AI Frontend Integration

## Epic Summary

| Özellik | Değer |
|---------|-------|
| Epic ID | E7 |
| Epic Name | AI Frontend Integration |
| Total SP | 7 |
| Stories | 4 |
| Priority | P1 |
| Dependencies | E6 (AI Email Parsing - ✅ Complete) |

---

## 1. Goals and Background

### 1.1 Problem Statement

E6 Epic ile backend'e AI-powered email parsing özellikleri eklendi:

- Email classification (stop_sale, reservation, other)
- Stop sale extraction with Gemini 2.0 Flash
- Confidence scoring ve fallback mechanism

Ancak bu özellikler henüz frontend'de kullanıcıya sunulmuyor:

- ❌ AI servisinin aktif olup olmadığı görünmüyor
- ❌ Stop sale kayıtlarında AI/Regex farkı belli değil
- ❌ Manual re-parse imkanı yok
- ❌ AI extraction sonuçlarını preview edemiyoruz

### 1.2 Goals

1. **Visibility**: AI servis durumunu kullanıcıya göster
2. **Transparency**: AI vs Regex parsing farkını göster
3. **Control**: Manual re-parse ve extraction imkanı sun
4. **Configuration**: AI threshold ayarlarını yönet

### 1.3 Success Metrics

| Metric | Target |
|--------|--------|
| AI Status visibility | 100% of authenticated users |
| Confidence display | All stop sales with ai_parsed=true |
| Manual re-parse usage | N/A (feature availability) |
| Page load time impact | < 100ms additional |

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | AI Status Badge dashboard'da görünmeli | P0 |
| FR-2 | Stop sales listesinde confidence badge | P0 |
| FR-3 | Parse method indicator (AI/Regex) | P1 |
| FR-4 | Email preview'da AI extraction | P1 |
| FR-5 | Manual re-parse button | P2 |
| FR-6 | AI Settings sayfası | P2 |

### 2.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | AI status response time | < 500ms |
| NFR-2 | Classification response time | < 2s |
| NFR-3 | Extraction response time | < 3s |
| NFR-4 | Mobile responsive | All new components |
| NFR-5 | Error handling | All AI operations |

---

## 3. API Dependencies

### 3.1 Backend Endpoints (E6 - Existing)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/ai/status` | GET | ✅ Available |
| `/ai/classify` | POST | ✅ Available |
| `/ai/extract-stop-sale` | POST | ✅ Available |

### 3.2 Backend Endpoints (To Be Added)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stop-sales/{id}/reparse` | POST | Manual re-parse trigger |

### 3.3 Database Schema Changes

```sql
-- stop_sales tablosuna AI metadata ekle
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS ai_parsed BOOLEAN DEFAULT FALSE;
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS ai_confidence DECIMAL(3,2);
ALTER TABLE stop_sales ADD COLUMN IF NOT EXISTS parse_method VARCHAR(20) DEFAULT 'regex';
```

---

## 4. Epic Stories

### E7.S1: AI Status Component (2 SP)

**As a** user  
**I want** to see if AI service is active  
**So that** I understand the parsing quality

**Acceptance Criteria:**

- [ ] AIStatusBadge component created
- [ ] Shows "AI Active: gemini-2.0-flash" when available
- [ ] Shows "AI Offline" when unavailable
- [ ] Badge visible on dashboard
- [ ] Loading state while checking

**Technical Notes:**

- Call GET /ai/status on mount
- Cache result for 5 minutes
- Use emerald/red color scheme

---

### E7.S2: Stop Sales AI Indicator (2 SP)

**As a** user  
**I want** to see which stop sales were parsed by AI  
**So that** I know the extraction confidence

**Acceptance Criteria:**

- [ ] ConfidenceBadge component created
- [ ] Shows "AI: 95%" or "Regex: 75%"
- [ ] Color coding: green (>70%), yellow (50-70%), red (<50%)
- [ ] Visible on stop sales list
- [ ] Backend returns ai_parsed, ai_confidence fields

**Technical Notes:**

- Requires database migration
- Update stop_sales API response

---

### E7.S3: Email AI Preview (2 SP)

**As a** user  
**I want** to preview AI extraction results before applying  
**So that** I can verify accuracy

**Acceptance Criteria:**

- [ ] EmailAIPreview component created
- [ ] Shows email subject and body
- [ ] "Classify" button triggers classification
- [ ] "Extract" button triggers extraction
- [ ] Shows extraction results (hotel, dates, rooms, reason)
- [ ] "Apply" button saves extraction
- [ ] Error handling for failed extractions

**Technical Notes:**

- Modal or slide-over component
- Integrate with emails page

---

### E7.S4: AI Settings Page (1 SP)

**As a** admin  
**I want** to configure AI settings  
**So that** I can adjust behavior

**Acceptance Criteria:**

- [ ] AI Settings page at /settings/ai
- [ ] Show AI status and model info
- [ ] Display supported languages
- [ ] Show confidence threshold (read-only for now)

**Technical Notes:**

- Future: Allow threshold adjustment
- Future: API key management (per-tenant)

---

## 5. Implementation Order

```
E7.S1 (AI Status) ──→ E7.S2 (Stop Sales Indicator)
                              │
                              ▼
E7.S4 (Settings) ←── E7.S3 (Email Preview)
```

**Rationale:**

1. S1 provides core AI visibility
2. S2 requires DB migration (can run parallel with S1)
3. S3 builds on S1/S2 patterns
4. S4 is lowest priority, simple implementation

---

## 6. Out of Scope

- AI model configuration (use default gemini-2.0-flash)
- Per-tenant API key management
- AI usage analytics/metrics
- Reservation extraction (E6 only does stop sales)

---

## 7. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI service downtime | Low confidence display | Show "AI Offline" badge |
| Slow AI responses | Poor UX | Loading states, timeout handling |
| Backend migration fails | Missing data | Make columns nullable |

---

## 8. Timeline

| Story | Est. Time | Dependencies |
|-------|-----------|--------------|
| E7.S1 | 2 hours | None |
| E7.S2 | 3 hours | DB migration |
| E7.S3 | 4 hours | E7.S1 |
| E7.S4 | 1 hour | E7.S1 |
| **Total** | **10 hours** | |

---

**Created:** 2025-12-31  
**Author:** Antigravity Agent  
**Status:** Ready for Development
