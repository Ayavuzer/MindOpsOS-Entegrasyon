# E6 AI Email Parsing - Test Plan

**Tarih:** 2025-12-31  
**Versiyon:** v1.9.1-e6-ai-parsing  
**Tester:** Manual  

---

## 1. Test Ortamı

### 1.1 Production Endpoints

```
Base URL: https://entegrasyon.mindops.net
API Base: kubectl port-forward -n entegrasyon deployment/entegrasyon-api 8081:8080
```

### 1.2 Test Araçları

- `curl` - API endpoint testi
- `kubectl` - Pod erişimi
- Browser - Frontend panel

---

## 2. API Endpoint Testleri

### 2.1 AI Status Endpoint

**Endpoint:** `GET /ai/status`

| Test Case | Beklenen Sonuç | Komut |
|-----------|----------------|-------|
| TC-2.1.1: AI availability check | `available: true` | `curl -s http://localhost:8081/ai/status` |
| TC-2.1.2: Model name check | `model: gemini-2.0-flash` | - |

**Test Komutu:**

```bash
kubectl port-forward -n entegrasyon deployment/entegrasyon-api 8081:8080 &
sleep 3
curl -s http://localhost:8081/ai/status | jq .
kill %1
```

**Beklenen Çıktı:**

```json
{
  "available": true,
  "model": "gemini-2.0-flash"
}
```

---

### 2.2 Email Classification Endpoint

**Endpoint:** `POST /ai/classify`

#### TC-2.2.1: Stop Sale Email (English)

```bash
curl -s -X POST http://localhost:8081/ai/classify \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Mandarin Hotel - Stop Sale Notice",
    "body": "Dear Partners,\n\nMandarin Hotel is closed for sale from 15.04.2025 to 20.04.2025.\n\nBest regards"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "email_type": "stop_sale",
  "confidence": 0.6,
  "language": "en"
}
```

#### TC-2.2.2: Stop Sale Email (Turkish)

```bash
curl -s -X POST http://localhost:8081/ai/classify \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Mandarin Otel - Satış Kapatma",
    "body": "Sayın İş Ortaklarımız,\n\nMandarin Otel 15.04.2025 - 20.04.2025 tarihleri arasında satışa kapalıdır.\n\nSaygılarımızla"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "email_type": "stop_sale",
  "confidence": 0.6,
  "language": "tr"
}
```

#### TC-2.2.3: Reservation Email

```bash
curl -s -X POST http://localhost:8081/ai/classify \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Booking Confirmation - Voucher #12345",
    "body": "Dear Guest,\n\nYour reservation at Mandarin Hotel has been confirmed.\nCheck-in: 15.04.2025\nCheck-out: 20.04.2025\nGuests: John Doe"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "email_type": "reservation",
  "confidence": 0.6,
  "language": "en"
}
```

#### TC-2.2.4: Unknown Email Type

```bash
curl -s -X POST http://localhost:8081/ai/classify \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Monthly Newsletter",
    "body": "Check out our latest offers and promotions!"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "email_type": "other",
  "confidence": 0.5,
  "language": "en"
}
```

---

### 2.3 Stop Sale Extraction Endpoint

**Endpoint:** `POST /ai/extract-stop-sale`

#### TC-2.3.1: Full Stop Sale (English)

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Mandarin Hotel - Stop Sale 15.04.2025 - 20.04.2025",
    "body": "Dear Partners,\n\nPlease note that Mandarin Hotel is closed for sale from 15.04.2025 to 20.04.2025 for all room types due to renovation.\n\nBest regards,\nReservations Team",
    "email_date": "2025-04-10"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "hotel_name": "Mandarin",
  "date_from": "2025-04-15",
  "date_to": "2025-04-20",
  "room_types": [],
  "is_close": true,
  "reason": "renovation",
  "confidence": 1.0,
  "error": null
}
```

#### TC-2.3.2: Stop Sale with Room Types

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Grand Palace - Stop Sale DBL Rooms",
    "body": "Grand Palace Hotel\n\nDouble rooms (DBL) and Triple rooms (TRP) are closed from 01.05.2025 to 10.05.2025.\n\nReason: Full capacity",
    "email_date": "2025-04-25"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "hotel_name": "Grand Palace",
  "date_from": "2025-05-01",
  "date_to": "2025-05-10",
  "room_types": ["DBL", "TRP"],
  "is_close": true,
  "reason": "Full capacity",
  "confidence": 1.0
}
```

#### TC-2.3.3: Open Sale (Release)

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Sunset Beach - Rooms Released",
    "body": "Sunset Beach Resort\n\nAll rooms are now available again from 15.06.2025.\n\nOpen Sale until 30.06.2025",
    "email_date": "2025-06-10"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "hotel_name": "Sunset Beach",
  "date_from": "2025-06-15",
  "date_to": "2025-06-30",
  "is_close": false,
  "confidence": 0.75
}
```

#### TC-2.3.4: Turkish Stop Sale

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Rixos Premium - Satış Kapatma",
    "body": "Değerli Acentelerimiz,\n\nRixos Premium Belek otelimiz 20.07.2025 - 25.07.2025 tarihleri arasında tadilat nedeniyle satışa kapalıdır.\n\nTüm oda tipleri etkilenmiştir.\n\nSaygılarımızla,\nRezarvasyon Departmanı",
    "email_date": "2025-07-15"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "hotel_name": "Rixos Premium Belek",
  "date_from": "2025-07-20",
  "date_to": "2025-07-25",
  "room_types": [],
  "is_close": true,
  "reason": "tadilat",
  "confidence": 1.0
}
```

#### TC-2.3.5: Russian Stop Sale

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Анталия Резорт - Стоп-продажа",
    "body": "Уважаемые партнёры,\n\nОтель Анталия Резорт закрыт на продажу с 01.08.2025 по 10.08.2025.\n\nПричина: ремонт",
    "email_date": "2025-07-25"
  }' | jq .
```

**Beklenen:**

```json
{
  "success": true,
  "hotel_name": "Анталия Резорт",
  "date_from": "2025-08-01",
  "date_to": "2025-08-10",
  "is_close": true,
  "reason": "ремонт",
  "confidence": 1.0
}
```

#### TC-2.3.6: Invalid/Missing Data

```bash
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Hello World",
    "body": "This is just a random email with no stop sale information."
  }' | jq .
```

**Beklenen:**

```json
{
  "success": false,
  "error": "Could not parse stop sale..."
}
```

---

## 3. Integration Tests

### 3.1 Full Email Processing Flow

Bu test, yeni bir email'in sistemde nasıl işlendiğini test eder.

#### TC-3.1.1: Email Parse → Stop Sale Create

1. Yeni pending email oluştur (DB'de)
2. Parse endpoint'ini çağır
3. Stop sale kaydının oluştuğunu doğrula
4. Method'un "ai" olduğunu doğrula

```sql
-- 1. Test email oluştur
INSERT INTO emails (tenant_id, subject, body_text, email_type, status, received_at)
VALUES (1, 'Test Hotel - Stop Sale', 'Test Hotel is closed from 01.01.2026 to 05.01.2026', 'stopsale', 'pending', NOW());

-- 2. Email ID'yi al
SELECT id FROM emails WHERE subject = 'Test Hotel - Stop Sale' ORDER BY id DESC LIMIT 1;

-- 3. Parse et (API üzerinden veya service call)

-- 4. Stop sale kontrolü
SELECT * FROM stop_sales WHERE hotel_name LIKE '%Test Hotel%' ORDER BY id DESC LIMIT 1;
```

---

## 4. Fallback Tests

### 4.1 AI Unavailable Scenario

**Senaryo:** GEMINI_API_KEY olmadan fallback çalışmalı

```bash
# Geçici olarak API key'i kaldır
kubectl set env deployment/entegrasyon-api -n entegrasyon GEMINI_API_KEY=""
kubectl rollout status deployment/entegrasyon-api -n entegrasyon

# Test
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Mandarin Hotel - Stop Sale 15.04.2025",
    "body": "Mandarin Hotel closed 15.04.2025 - 20.04.2025"
  }' | jq .

# API key'i geri yükle
kubectl set env deployment/entegrasyon-api -n entegrasyon GEMINI_API_KEY="<key>"
```

**Beklenen:** Regex fallback ile başarılı extraction

---

## 5. Performance Tests

### 5.1 Response Time

| Test Case | Max Süre |
|-----------|----------|
| /ai/status | < 100ms |
| /ai/classify | < 2000ms |
| /ai/extract-stop-sale | < 3000ms |

```bash
# Response time ölçümü
time curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{"subject":"Test","body":"Test Hotel closed 01.01.2025 - 05.01.2025"}' > /dev/null
```

---

## 6. Edge Cases

### 6.1 Date Format Variations

| Format | Örnek | Test |
|--------|-------|------|
| DD.MM.YYYY | 15.04.2025 | ✓ |
| DD/MM/YYYY | 15/04/2025 | ✓ |
| YYYY-MM-DD | 2025-04-15 | ✓ |
| DD-MM-YYYY | 15-04-2025 | ✓ |
| DD.MM.YY | 15.04.25 | ✓ |

### 6.2 Hotel Name Variations

| Format | Örnek |
|--------|-------|
| With suffix | Mandarin Hotel |
| Without suffix | Mandarin |
| Turkish | Rixos Premium Belek |
| With special chars | Grand Hotel & Spa |

### 6.3 Multi-language Keywords

| Language | Stop Sale | Open Sale |
|----------|-----------|-----------|
| English | stop sale, closed | open, release, available |
| Turkish | satış kapatma, kapalı | açık, satış açık |
| Russian | стоп-продажа, закрыт | открыто |
| German | verkaufsstopp | verfügbar |

---

## 7. Test Checklist

### ✅ API Tests

- [ ] TC-2.1.1: AI status - available
- [ ] TC-2.1.2: AI status - model name
- [ ] TC-2.2.1: Classify - stop sale (EN)
- [ ] TC-2.2.2: Classify - stop sale (TR)
- [ ] TC-2.2.3: Classify - reservation
- [ ] TC-2.2.4: Classify - unknown
- [ ] TC-2.3.1: Extract - full stop sale
- [ ] TC-2.3.2: Extract - with room types
- [ ] TC-2.3.3: Extract - open sale
- [ ] TC-2.3.4: Extract - Turkish
- [ ] TC-2.3.5: Extract - Russian
- [ ] TC-2.3.6: Extract - invalid data

### ✅ Integration Tests

- [ ] TC-3.1.1: Email parse flow

### ✅ Fallback Tests

- [ ] TC-4.1.1: AI unavailable fallback

### ✅ Performance Tests

- [ ] TC-5.1.1: Response time < 3s

---

## 8. Test Execution

### Quick Test Script

```bash
#!/bin/bash
# E6 AI Email Parsing - Quick Test

echo "🚀 Starting E6 Test Suite..."

# Port forward
kubectl port-forward -n entegrasyon deployment/entegrasyon-api 8081:8080 &
PF_PID=$!
sleep 3

echo ""
echo "1️⃣ AI Status Test"
curl -s http://localhost:8081/ai/status | jq .

echo ""
echo "2️⃣ Classification Test (English)"
curl -s -X POST http://localhost:8081/ai/classify \
  -H "Content-Type: application/json" \
  -d '{"subject":"Hotel X - Stop Sale","body":"Hotel X is closed from 01.01.2025"}' | jq .

echo ""
echo "3️⃣ Extraction Test (Full)"
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{"subject":"Mandarin - Stop Sale","body":"Mandarin Hotel closed 15.04.2025 - 20.04.2025 renovation"}' | jq .

echo ""
echo "4️⃣ Extraction Test (Turkish)"
curl -s -X POST http://localhost:8081/ai/extract-stop-sale \
  -H "Content-Type: application/json" \
  -d '{"subject":"Rixos - Satış Kapatma","body":"Rixos Premium 20.07.2025 - 25.07.2025 tadilat"}' | jq .

# Cleanup
kill $PF_PID 2>/dev/null

echo ""
echo "✅ Test Suite Complete!"
```

---

## 9. Test Sonuçları

| Test ID | Sonuç | Notlar |
|---------|-------|--------|
| TC-2.1.1 | ⏳ | |
| TC-2.1.2 | ⏳ | |
| TC-2.2.1 | ⏳ | |
| TC-2.2.2 | ⏳ | |
| TC-2.2.3 | ⏳ | |
| TC-2.2.4 | ⏳ | |
| TC-2.3.1 | ⏳ | |
| TC-2.3.2 | ⏳ | |
| TC-2.3.3 | ⏳ | |
| TC-2.3.4 | ⏳ | |
| TC-2.3.5 | ⏳ | |
| TC-2.3.6 | ⏳ | |

---

**Hazırlayan:** Antigravity Agent  
**Tarih:** 2025-12-31
