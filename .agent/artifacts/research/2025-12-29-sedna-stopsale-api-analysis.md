# 🔬 Research: Sedna Stop Sales API Entegrasyonu

> **Tarih:** 2025-12-29
> **Araştırmacı:** Dr. Elena Vasquez
> **Depth:** Deep
> **Confidence:** High

---

## 📋 Executive Summary

Sedna Stop Sales API'si **iki aşamalı** bir entegrasyon yaklaşımı gerektirir. Mevcut uygulama basit bir `InsertStopSale` endpoint'i kullanıyor, ancak Postman koleksiyonunda görüldüğü üzere doğru entegrasyon için:

1. Önce boş alt dizilerle ana kayıt oluşturulmalı
2. Sonra dönen `RecId` ile alt kayıtlar (Room, Operator, Board, Market) eklenmeli

---

## 🎯 Research Question

**Ana Soru:** Sedna Stop Sales API'sine tam entegrasyon nasıl yapılır?

**Alt Sorular:**

1. API endpoint'leri nelerdir?
2. Authentication nasıl çalışır?
3. Hangi referans verileri (Room, Board, Operator) gereklidir?
4. İki aşamalı kayıt süreci nasıl işler?

---

## 📊 Findings

### 1. API Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/Integratiion/AgencyLogin` | GET | Authentication - token almak için |
| `/api/Integratiion/GetRoomTypeList` | POST | Oda tipi listesi (operatorId gerekli) |
| `/api/Service2/GetBoardList` | GET | Pansiyon tipi listesi |
| `/api/Contract/CheckStopSaleState` | POST | Mevcut stop sale durumunu kontrol et |
| `/api/Contract/UpdateStopSale` | PUT | Stop sale oluştur/güncelle ⭐ |

### 2. Base URL

```
Test: http://test.kodsedna.com/SednaAgencyB2bApi
Prod: https://agencyb2b.sednabooking.com/SednaAgencyb2bApi (tahmin)
```

### 3. Authentication

```http
GET /api/Integratiion/AgencyLogin?username=7STAR&password=1234
```

**Credentials:**

- Username: Agency kodu (örn: "7STAR")
- Password: Agency şifresi

### 4. Referans Veriler

#### 4.1 Room Types (Oda Tipleri)

```http
POST /api/Integratiion/GetRoomTypeList?operatorId=571
```

**Örnek Response (tahmin):**

```json
[
  {"RoomTypeId": 63, "Code": "STDSV", "Name": "Standard Sea View"},
  {"RoomTypeId": 1364, "Code": "STDLV", "Name": "Standard Land View"},
  ...
]
```

#### 4.2 Board Types (Pansiyon Tipleri)

```http
GET /api/Service2/GetBoardList
```

**Örnek Response (tahmin):**

```json
[
  {"BoardId": 1, "Code": "AI", "Name": "All Inclusive"},
  {"BoardId": 37, "Code": "UAI", "Name": "Ultra All Inclusive"},
  ...
]
```

### 5. UpdateStopSale Request Yapısı ⭐

#### 5.1 Aşama 1: Ana Kayıt Oluştur (RecId=0)

```json
{
  "RecId": 0,                              // Yeni kayıt = 0
  "HotelId": 18,                           // Otel ID (Sedna'dan)
  "BeginDate": "2026-01-25T00:00:00",      // Başlangıç tarihi
  "EndDate": "2026-01-25T00:00:00",        // Bitiş tarihi  
  "DeclareDate": "2025-12-29T00:00:00",    // Bildirim tarihi
  "Active": 0,                             // 0=Aktif, 1=Pasif?
  "RecordUser": "Sedna",                   // Kaydeden kullanıcı
  "RecordSource": 0,                       // Kaynak (0=API?)
  "StopType": 0,                           // 0=StopSale, 1=OpenSale?
  "Authority": 207,                        // Yetki ID (?)
  "RoomRemark": "STDSV,STDLV",             // Oda kodları (görsel)
  "OperatorRemark": "7STAR,",              // Acenta (görsel, SONA VİRGÜL!)
  "BoardRemark": "UAI",                    // Pansiyon (görsel)
  "State": 1,                              // 1=Active
  
  // ⚠️ KRİTİK: İlk kayıtta boş gönder
  "StopSaleRooms": [],
  "StopSaleOperators": [],
  "StopSaleBoards": [],
  "StopSaleMarkets": []
}
```

**Response:**

```json
{
  "ErrorType": 0,
  "Message": "Success",
  "RecId": 823259  // ← Bu ID'yi kaydet!
}
```

#### 5.2 Aşama 2: Alt Kayıtları Ekle

```json
{
  "RecId": 823259,                          // ← Aşama 1'den gelen ID
  "HotelId": 18,
  "BeginDate": "2026-01-25T00:00:00",
  "EndDate": "2026-01-25T00:00:00",
  "DeclareDate": "2025-12-29T00:00:00",
  "Active": 0,
  "RecordUser": "Sedna",
  "RecordSource": 0,
  "StopType": 0,
  "Authority": 207,
  "RoomRemark": "STDSV,STDLV",
  "OperatorRemark": "7STAR,",
  "BoardRemark": "UAI",
  "State": 1,
  
  // ⚠️ ŞİMDİ DOLU GÖNDERİYORUZ
  "StopSaleRooms": [
    { "RoomTypeId": 63, "State": 1, "StopSaleId": 823259 }
  ],
  "StopSaleOperators": [
    { "OperatorId": 571, "State": 1, "StopSaleId": 823259 }
  ],
  "StopSaleBoards": [
    { "BoardId": 1, "State": 1, "StopSaleId": 823259 }
  ],
  "StopSaleMarkets": [
    { "MarketId": 10, "State": 1, "StopSaleId": 823259 }
  ]
}
```

### 6. CheckStopSaleState Request

Mevcut stop sale durumunu kontrol etmek için:

```json
{
  "hotelId": 18,
  "beginDate": "2025-12-29T00:00:00",
  "endDate": "2025-12-29T00:00:00",
  "operatorList": [571],
  "roomList": [63, 1364, 1389],
  "boardList": [1, 37]
}
```

---

## 📋 Veri Eşleme (Data Mapping)

### Email Parsing → Sedna API

| Email Field | Sedna Field | Notes |
|-------------|-------------|-------|
| `hotel_name` | `HotelId` | ⚠️ Hotel lookup gerekli |
| `date_from` | `BeginDate` | Format: ISO 8601 |
| `date_to` | `EndDate` | Format: ISO 8601 |
| `room_type` | `RoomRemark` + `StopSaleRooms` | Room ID lookup gerekli |
| `is_close` | `StopType` | true=0 (stop), false=1 (open)? |
| `reason` | - | API'de yok |
| - | `OperatorId` | Tenant config'den |
| - | `Authority` | Tenant config'den |

### Gerekli Lookup'lar

| Lookup | Source | Cache? |
|--------|--------|--------|
| Hotel Name → HotelId | `/api/Hotel/Search` veya cache | ✅ Günlük |
| Room Code → RoomTypeId | `/api/Integratiion/GetRoomTypeList` | ✅ Günlük |
| Board Code → BoardId | `/api/Service2/GetBoardList` | ✅ Haftalık |
| Operator Code → OperatorId | Tenant config | ❌ Static |

---

## 🔄 Entegrasyon Akışı

```
┌─────────────────────────────────────────────────────────────────────┐
│                     STOP SALE SYNC FLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. PREPARE DATA                                                     │
│     ├─ Get stop_sale record from DB                                 │
│     ├─ Lookup HotelId (by hotel_name)                               │
│     ├─ Parse RoomRemark → Get RoomTypeIds                           │
│     ├─ Get OperatorId from tenant config                            │
│     └─ Get BoardIds (or use default)                                │
│                                                                      │
│  2. CREATE MAIN RECORD (RecId=0)                                    │
│     ├─ POST /api/Contract/UpdateStopSale                            │
│     ├─ Body: Main record + EMPTY child arrays                       │
│     └─ Response: { RecId: 823259 }                                  │
│                                                                      │
│  3. UPDATE WITH CHILDREN (RecId=823259)                             │
│     ├─ PUT /api/Contract/UpdateStopSale                             │
│     ├─ Body: Main record + FILLED child arrays                      │
│     │   └─ Each child has: StopSaleId = 823259                      │
│     └─ Response: { Success }                                        │
│                                                                      │
│  4. UPDATE LOCAL DB                                                  │
│     ├─ SET sedna_synced = true                                      │
│     ├─ SET sedna_rec_id = 823259                                    │
│     └─ SET sedna_sync_at = NOW()                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Kritik Notlar

### 1. OperatorRemark Sonuna Virgül

```json
"OperatorRemark": "7STAR,"  // ✅ Doğru - Sonunda virgül var!
"OperatorRemark": "7STAR"   // ❌ Yanlış - Arayüzde görünmeyebilir
```

### 2. İki Aşamalı Kayıt Zorunlu

```
❌ YANLIŞ: Tek seferde boş olmayan child array göndermek
            → "Object reference not set" hatası alınır

✅ DOĞRU:  1. Önce boş child array ile kaydet → RecId al
           2. Sonra RecId ile dolu child array gönder
```

### 3. Child Kayıtlarda StopSaleId

```json
{
  "StopSaleRooms": [
    {
      "RoomTypeId": 63,
      "State": 1,
      "StopSaleId": 823259  // ⚠️ Bu ana kaydın ID'si OLMALI!
    }
  ]
}
```

---

## 📊 Mevcut Kod vs Doğru Implementasyon

### Mevcut Kod (Eksik)

```python
# apps/api/sedna/service.py - sync_stop_sale()

response = await client.post(
    f"{sedna_config['api_url']}/api/StopSale/InsertStopSale",  # ❌ Yanlış endpoint
    json={
        "HotelId": hotel_id,
        "BeginDate": stop_sale["date_from"].strftime("%Y-%m-%d"),
        "EndDate": stop_sale["date_to"].strftime("%Y-%m-%d"),
        "IsClose": stop_sale["is_close"],
        # ❌ Eksik: RoomRemark, OperatorRemark, BoardRemark
        # ❌ Eksik: Two-phase save
        # ❌ Eksik: Child records
    },
)
```

### Doğru Implementasyon (Önerilen)

```python
async def sync_stop_sale(self, tenant_id: int, stop_sale_id: int) -> SyncResult:
    # 1. Get data
    stop_sale = await self._get_stop_sale(stop_sale_id, tenant_id)
    sedna_config = await self._get_sedna_config(tenant_id)
    
    # 2. Lookups
    hotel_id = await self._lookup_hotel_id(stop_sale["hotel_name"])
    room_type_ids = await self._lookup_room_types(stop_sale["room_type"])
    operator_id = sedna_config["operator_id"]
    
    # 3. Phase 1: Create main record with EMPTY children
    phase1_body = {
        "RecId": 0,
        "HotelId": hotel_id,
        "BeginDate": stop_sale["date_from"].isoformat(),
        "EndDate": stop_sale["date_to"].isoformat(),
        "DeclareDate": datetime.now().isoformat(),
        "Active": 0,
        "RecordUser": "Entegrasyon",
        "RecordSource": 0,
        "StopType": 0 if stop_sale["is_close"] else 1,
        "Authority": sedna_config.get("authority_id", 207),
        "RoomRemark": stop_sale["room_type"] or "",
        "OperatorRemark": f"{sedna_config['operator_code']},",  # ⚠️ Virgül!
        "BoardRemark": "",
        "State": 1,
        "StopSaleRooms": [],
        "StopSaleOperators": [],
        "StopSaleBoards": [],
        "StopSaleMarkets": [],
    }
    
    response1 = await client.put(
        f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
        json=phase1_body,
    )
    rec_id = response1.json().get("RecId")
    
    # 4. Phase 2: Update with filled children
    phase2_body = {**phase1_body, "RecId": rec_id}
    phase2_body["StopSaleRooms"] = [
        {"RoomTypeId": rt_id, "State": 1, "StopSaleId": rec_id}
        for rt_id in room_type_ids
    ]
    phase2_body["StopSaleOperators"] = [
        {"OperatorId": operator_id, "State": 1, "StopSaleId": rec_id}
    ]
    
    response2 = await client.put(
        f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
        json=phase2_body,
    )
    
    # 5. Update local DB
    await self._update_sync_status(stop_sale_id, rec_id)
    
    return SyncResult(success=True, sedna_rec_id=rec_id)
```

---

## 💡 Recommendation

### Primary Recommendation

**Two-Phase UpdateStopSale implementasyonunu ekle:**

1. Mevcut `sync_stop_sale()` metodunu güncelle
2. Reference data cache sistemi ekle (Room, Board, Operator)
3. Tenant config'e Sedna operator_id ve authority_id ekle

**Güven Seviyesi:** High
**Gerekçe:** Postman collection'daki örnek ve yorumlar açıkça iki aşamalı kayıt sürecini gösteriyor

### Implementation Priority

| Task | Priority | Story Points |
|------|----------|--------------|
| UpdateStopSale endpoint değiştir | P0 | 2 |
| İki aşamalı kayıt implementasyonu | P0 | 3 |
| Room/Board cache sistemi | P1 | 3 |
| Tenant config update (operator_id) | P1 | 1 |
| CheckStopSaleState entegrasyonu | P2 | 2 |

### Risk/Consideration

⚠️ **Test Ortamı:** `test.kodsedna.com` test ortamıdır. Production URL'i farklı olabilir.

⚠️ **Authentication:** Login endpoint'i token döndürüyor mu yoksa session-based mı, netleştirilmeli.

⚠️ **Hotel ID Mapping:** Hotel name → HotelId eşlemesi için ayrı bir lookup endpoint'i gerekebilir.

---

## 📚 Sources

1. **StopSale.postman_collection.json** - Tier 1 (Primary source)
   - Path: `docs/StopSale.postman_collection.json`
   - Created by Sedna team

2. **Current Implementation** - Tier 1 (Internal)
   - `apps/api/sedna/service.py`
   - `src/parsers/email_parser.py`

---

## 📁 Sonraki Adımlar

### Story E3: Sedna Stop Sale Full Integration

```markdown
## Stories

1. **E3.S1:** Update sync_stop_sale to use UpdateStopSale endpoint
2. **E3.S2:** Implement two-phase save pattern
3. **E3.S3:** Add room/board type cache service
4. **E3.S4:** Update tenant config for Sedna operator settings
5. **E3.S5:** Integration testing with test.kodsedna.com
```

---

*Research completed in 15 minutes*
