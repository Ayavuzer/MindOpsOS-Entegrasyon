# 🔬 Research: Stop Sales & Rezervasyon Mail İçerikleri - Sedna API Mapping

> **Tarih:** 2025-12-29
> **Araştırmacı:** Dr. Elena Vasquez
> **Depth:** Deep
> **Confidence:** High
> **Proje:** MindOpsOS-Entegrasyon

---

## 📋 Executive Summary

Bu rapor, Juniper operatörlerinden gelen stop sale ve rezervasyon e-maillerinin tam içerik analizini ve bu içeriklerin Sedna API'ye nasıl map edildiğini detaylandırmaktadır. Mevcut sistemde email parsing → database → Sedna API sync akışı incelenmiştir.

---

## 📧 1. STOP SALE E-MAİL ANALİZİ

### 1.1 Örnek E-mail İçeriği

```
Subject: STOP SALE - Mandarin resort

Body:
Dear Partner, 
Greetings kindly stop sale all rooms, (13.04.25, Till 18.04.25). 
Please update your system accordingly
```

### 1.2 Parser Tarafından Çıkarılan Alanlar

| Email Field | Parser Pattern | Örnek Değer |
|-------------|----------------|-------------|
| **Hotel Name** | `([A-Za-z\s&'-]+)\s+(?:Hotel\|Otel\|Resort)` | `Mandarin Resort` |
| **Date From** | `(\d{1,2}[./]\d{1,2}[./]\d{2,4})` | `13.04.25` → `2025-04-13` |
| **Date To** | `(\d{1,2}[./]\d{1,2}[./]\d{2,4})` | `18.04.25` → `2025-04-18` |
| **Room Types** | `(?:Room[\s]?Type\|Oda[\s]?Tipi)[:\s]+(.+?)` | `null` (all rooms) |
| **Board Types** | `(?:Board\|Pansiyon)[:\s]+(.+?)` | `null` (all boards) |
| **Is Close** | Keyword detection (`stop sale` vs `open sale`) | `true` |
| **Reason** | `(?:Reason\|Sebep)[:\s]+(.+?)` | `null` |

### 1.3 Database'e Kaydedilen Yapı (stop_sales tablosu)

```sql
CREATE TABLE stop_sales (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL,
    email_id        INTEGER REFERENCES emails(id),
    hotel_name      VARCHAR(255),        -- "Mandarin Resort"
    date_from       DATE,                -- 2025-04-13
    date_to         DATE,                -- 2025-04-18
    room_type       VARCHAR(255),        -- NULL veya "DBL, SGL"
    is_close        BOOLEAN DEFAULT true,-- true = stop, false = open
    reason          TEXT,
    status          VARCHAR(50),         -- pending, synced, failed
    sedna_hotel_id  INTEGER,             -- Manuel/fuzzy match ile atanan
    sedna_synced    BOOLEAN DEFAULT false,
    sedna_rec_id    INTEGER,             -- Sedna'dan dönen RecId
    created_at      TIMESTAMP
);
```

### 1.4 Sedna API Payload (UpdateStopSale)

```json
{
    "RecId": 0,                              // Phase 1: 0, Phase 2: returned ID
    "HotelId": 28,                           // Sedna Hotel ID (mapping gerekli)
    "BeginDate": "2025-04-13T00:00:00",      // date_from
    "EndDate": "2025-04-18T00:00:00",        // date_to
    "DeclareDate": "2025-12-29T00:00:00",    // Bugünün tarihi
    "Active": 0,
    "RecordUser": "Entegrasyon",
    "RecordSource": 0,
    "StopType": 0,                           // 0=Stop, 1=Open
    "Authority": 207,                        // Yetkili ID
    "RoomRemark": "",                        // room_type string
    "OperatorRemark": "7STAR,",              // ⚠️ Virgül ile bitmeli!
    "BoardRemark": "",
    "State": 1,
    "StopSaleRooms": [                       // Phase 2'de dolu
        {
            "RoomTypeId": 3,
            "State": 1,
            "StopSaleId": 12345
        }
    ],
    "StopSaleOperators": [                   // Phase 2'de dolu
        {
            "OperatorId": 571,
            "State": 1,
            "StopSaleId": 12345
        }
    ],
    "StopSaleBoards": [],
    "StopSaleMarkets": []
}
```

---

## 📋 2. REZERVASYON E-MAİL ANALİZİ

### 2.1 Rezervasyon Kaynağı

Rezervasyonlar **PDF attachment** olarak gelir (Juniper voucher). Email body'si değil, PDF içeriği parse edilir.

### 2.2 PDF'den Çıkarılan Alanlar

| PDF Field | Parser Pattern | Örnek Değer |
|-----------|----------------|-------------|
| **Voucher No** | `(?:Voucher\|Booking\|Reference)[\s#:№]*([A-Z0-9]{4,20})` | `JNP123456` |
| **Hotel Name** | `(?:Hotel\|Otel)[:\s]+(.+?)(?:\n\|$)` | `Grand Hotel Antalya` |
| **Check-in** | `(?:Check[\s-]?in\|Giriş)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})` | `01.05.2025` |
| **Check-out** | `(?:Check[\s-]?out\|Çıkış)[:\s]+(\d{1,2}[./]\d{1,2}[./]\d{2,4})` | `07.05.2025` |
| **Room Type** | `(?:Room[\s]?Type\|Oda[\s]?Tipi)[:\s]+(.+?)` | `Double Room` → `DBL` |
| **Board Type** | `(?:Board\|Meal[\s]?Plan)[:\s]+(.+?)` | `All Inclusive` → `AI` |
| **Adults** | `(?:Adults?\|Yetişkin)[:\s]+(\d+)` | `2` |
| **Children** | `(?:Child(?:ren)?\|Çocuk)[:\s]+(\d+)` | `1` |
| **Total Price** | `(?:Total\|Toplam)[:\s]*([€$₺]?\s*[\d,.']+)` | `€1,234.56` |
| **Currency** | `([€$₺£])\|\\b(EUR\|USD\|TRY)\\b` | `EUR` |
| **Guests** | `(?:Mr\\.?\|Mrs\\.?)\\s+([A-Z][A-Za-z]+)\\s+([A-Z][A-Za-z]+)` | `Mr. John SMITH` |

### 2.3 Database'e Kaydedilen Yapı (reservations tablosu)

```sql
CREATE TABLE reservations (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL,
    voucher_no      VARCHAR(50) UNIQUE,      -- "JNP123456"
    hotel_name      VARCHAR(255),            -- "Grand Hotel Antalya"
    check_in        DATE,                    -- 2025-05-01
    check_out       DATE,                    -- 2025-05-07
    room_type       VARCHAR(50),             -- "DBL"
    board_type      VARCHAR(10),             -- "AI"
    adults          INTEGER DEFAULT 2,
    children        INTEGER DEFAULT 0,
    total_price     DECIMAL(10,2),           -- 1234.56
    currency        VARCHAR(3),              -- "EUR"
    guests          JSONB,                   -- [{title,first_name,last_name}]
    source_email_id INTEGER,
    status          VARCHAR(50),             -- pending, synced
    sedna_synced    BOOLEAN DEFAULT false,
    sedna_rec_id    INTEGER,
    created_at      TIMESTAMP
);
```

### 2.4 Sedna API Payload (InsertReservation)

```json
[{
    "Voucher": "JNP123456",              // voucher_no
    "CheckinDate": "2025-05-01",         // check_in (ISO format)
    "CheckOutDate": "2025-05-07",        // check_out
    "HotelId": 28,                       // Sedna Hotel ID (mapping gerekli!)
    "OperatorId": 571,                   // Tenant'ın operator_id'si
    "Adult": 2,                          // adults
    "Child": 1,                          // children
    "BoardId": 1,                        // AI=1, FB=2, HB=4 (mapping gerekli!)
    "RoomTypeId": 3,                     // Sedna Room Type ID (mapping gerekli!)
    "SourceId": "MO-123",                // Internal reference
    "Amount": 1234.56,                   // total_price
    "SaleDate": "2025-01-15",            // Satış tarihi
    "Customers": [
        {
            "Title": "Mr",               // Guest title
            "FirstName": "JOHN",         // guest.first_name
            "LastName": "SMITH",         // guest.last_name
            "BirthDate": "1985-06-15",   // (optional)
            "Age": 39,                   // (optional)
            "PassNo": "",                // (optional)
            "Nationality": "UKRAINE",    // (optional)
            "NationalityId": 79          // (optional, mapping gerekli)
        }
    ],
    
    // Transfer bilgileri (optional)
    "ArrivalFlightNumber": "",
    "DepartureFlightNumber": "",
    "ArrivalFlightTime": "",
    "DepartureFlightTime": "",
    "ArrTransferType": 0,
    "DepTransferType": 0,
    "IsArrivalTransfer": 0,
    "IsDepartureTransfer": 0,
    
    // Notes
    "HotelRemark": "",
    "ReservationRemark": "",
    "CheckContract": true
}]
```

---

## 🔄 3. FIELD MAPPING TABLİSİ

### 3.1 Stop Sale Mapping

| Email/DB Field | Sedna API Field | Mapping Logic |
|----------------|-----------------|---------------|
| `hotel_name` | `HotelId` | 🔴 **Fuzzy Search Required** |
| `date_from` | `BeginDate` | ISO format + `T00:00:00` |
| `date_to` | `EndDate` | ISO format + `T00:00:00` |
| `room_type` | `StopSaleRooms[]` | 🔴 **Room Type ID Lookup Required** |
| `is_close` | `StopType` | `true → 0`, `false → 1` |
| `-` | `OperatorId` | Tenant settings'ten |
| `-` | `Authority` | Default: 207 |

### 3.2 Reservation Mapping

| Email/DB Field | Sedna API Field | Mapping Logic |
|----------------|-----------------|---------------|
| `hotel_name` | `HotelId` | 🔴 **Fuzzy Search Required** |
| `voucher_no` | `Voucher` | Direct |
| `check_in` | `CheckinDate` | ISO format (YYYY-MM-DD) |
| `check_out` | `CheckOutDate` | ISO format |
| `adults` | `Adult` | Integer |
| `children` | `Child` | Integer |
| `room_type` | `RoomTypeId` | 🔴 **Map: DBL→3, SGL→1, etc.** |
| `board_type` | `BoardId` | 🟡 **Map: AI→1, FB→2, HB→4** |
| `total_price` | `Amount` | Decimal |
| `guests[].first_name` | `Customers[].FirstName` | UPPERCASE |
| `guests[].last_name` | `Customers[].LastName` | UPPERCASE |

### 3.3 ID Mapping Tabloları

#### Board Type Mapping

| Email Value | Sedna BoardId |
|-------------|---------------|
| AI, All Inclusive | 1 |
| FB, Full Board | 2 |
| HB, Half Board | 4 |
| BB, Bed & Breakfast | 3 |
| RO, Room Only | 5 |

#### Room Type Mapping (Örnek)

| Email Value | Sedna RoomTypeId |
|-------------|------------------|
| DBL, Double | 3 |
| SGL, Single | 1 |
| TRP, Triple | 4 |
| FAM, Family | 516 |
| SUI, Suite | 10 |

> ⚠️ **Not:** Room type ID'ler otele göre değişir! Her otel için `GetHotelRoomTypelistAll` API'si çağrılmalı.

---

## 📊 4. DATA FLOW DİAGRAMI

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EMAIL PROCESSING FLOW                          │
└─────────────────────────────────────────────────────────────────────────┘

     ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
     │   EMAIL     │         │  DATABASE   │         │  SEDNA API  │
     │   INBOX     │         │             │         │             │
     └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
            │                       │                       │
            │  1. Fetch Email       │                       │
            ├──────────────────────►│                       │
            │                       │                       │
            │  2. Store in emails   │                       │
            │     table             │                       │
            │                       │                       │
            │                       │                       │
   ┌────────┴────────┐              │                       │
   │   STOP SALE?    │              │                       │
   │   (text/html)   │              │                       │
   └────────┬────────┘              │                       │
            │ YES                   │                       │
            │  3. Parse Body        │                       │
            ├──────────────────────►│                       │
            │     - hotel_name      │                       │
            │     - date_from/to    │                       │
            │     - room_types      │                       │
            │     - is_close        │                       │
            │                       │                       │
            │  4. Insert stop_sales │                       │
            │                       │                       │
            │                       │  5. User clicks       │
            │                       │     "Sync"            │
            │                       ├──────────────────────►│
            │                       │                       │
            │                       │  6. Find Hotel ID     │
            │                       │     (Fuzzy Match)     │
            │                       │◄──────────────────────┤
            │                       │                       │
            │                       │  7. Build Payload     │
            │                       │                       │
            │                       │  8. PUT UpdateStopSale│
            │                       ├──────────────────────►│
            │                       │    (Phase 1 + 2)      │
            │                       │                       │
            │                       │  9. Save RecId        │
            │                       │◄──────────────────────┤
            │                       │                       │
            │                       │                       │
   ┌────────┴────────┐              │                       │
   │  RESERVATION?   │              │                       │
   │  (PDF attach)   │              │                       │
   └────────┬────────┘              │                       │
            │ YES                   │                       │
            │  3. Parse PDF         │                       │
            ├──────────────────────►│                       │
            │     - voucher_no      │                       │
            │     - hotel_name      │                       │
            │     - check_in/out    │                       │
            │     - guests[]        │                       │
            │     - price           │                       │
            │                       │                       │
            │  4. Insert            │                       │
            │     reservations      │                       │
            │                       │                       │
            │                       │  5-9. Similar flow    │
            │                       │  POST InsertReservation│
            │                       ├──────────────────────►│
            │                       │                       │
            └───────────────────────┴───────────────────────┘
```

---

## 🔴 5. KRİTİK MAPPING GEREKSİNİMLERİ

### 5.1 Hotel ID Mapping (En Kritik!)

**Problem:** Email'de "Mandarin Resort" yazıyor, Sedna'da bu otelin ID'si nedir?

**Çözüm (Mevcut - E4):**

1. `HotelSearchService` ile fuzzy match yap
2. Kullanıcıya benzer otelleri göster
3. Seçilen ID'yi `stop_sales.sedna_hotel_id` alanına kaydet
4. Sonraki sync'lerde bu ID'yi kullan

### 5.2 Room Type Mapping

**Problem:** Email'de "DBL, SGL" yazıyor, Sedna'da bunların ID'leri nedir?

**Çözüm (Mevcut):**

- `SednaCacheService.get_room_type_ids()` metodu
- Otel bazlı room type cache

### 5.3 Board Type Mapping

**Çözüm:** Static mapping (AI=1, FB=2, HB=4)

---

## 📈 6. MEVCUT SİSTEM DURUMU

| Bileşen | Durum | Notlar |
|---------|:-----:|--------|
| Email Fetch | ✅ | OAuth + IMAP çalışıyor |
| Stop Sale Parser | ✅ | Regex-based extraction |
| PDF Parser | ✅ | PyMuPDF ile çalışıyor |
| Hotel Fuzzy Match | ✅ | E4 epic ile tamamlandı |
| Stop Sale Sync | ⚠️ | Auth fix yapıldı (E5) |
| Reservation Sync | ❓ | Test edilmeli |
| Room Type Mapping | ⚠️ | Cache mekanizması var |
| UI Display | 🔄 | SyncModal çalışıyor |

---

## 💡 7. ÖNERİLER

### 7.1 Immediate Actions

1. **E5 Test:** Auth fix'in çalıştığını doğrula
2. **Endpoint Validation:** 404 alınırsa alternative path dene
3. **Reservation Test:** Bir rezervasyon sync'i test et

### 7.2 Future Improvements

1. **Email Template Detection:** Farklı operatör formatları için pattern ekle
2. **AI-Powered Parsing:** LLM ile parsing accuracy artır
3. **Mapping Cache:** Hotel/Room mapping'leri kalıcı olarak kaydet
4. **Validation UI:** Parse sonuçlarını kullanıcıya göster ve düzeltme imkanı ver

---

## 📚 Sources

1. `apps/api/emailfetch/parser.py` - Tier 1 (Source Code)
2. `src/parsers/email_parser.py` - Tier 1 (Source Code)
3. `src/parsers/pdf_parser.py` - Tier 1 (Source Code)
4. `apps/api/sedna/service.py` - Tier 1 (Source Code)
5. `docs/sedna-api-analysis.md` - Tier 1 (Internal Docs)
6. Production database analysis - Tier 1

---

*Research completed in 25 minutes*
