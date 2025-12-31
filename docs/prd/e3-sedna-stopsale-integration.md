# E3: Sedna Stop Sales Tam Entegrasyonu

> **Epic Owner:** Development Team
> **Created:** 2025-12-29
> **Status:** Draft
> **Total SP:** 13

---

## 🎯 Goals and Background

### Problem Statement

Mevcut `sync_stop_sale()` implementasyonu Sedna API'sinin beklediği formatta çalışmıyor:

1. **Yanlış Endpoint:** `/api/StopSale/InsertStopSale` yerine `/api/Contract/UpdateStopSale` kullanılmalı
2. **Eksik Two-Phase Save:** Sedna API'si iki aşamalı kayıt gerektiriyor
3. **Eksik Child Records:** StopSaleRooms, StopSaleOperators, StopSaleBoards eksik
4. **Eksik Lookups:** Room/Board ID'leri için cache sistemi yok

### Success Metrics

| Metric | Target |
|--------|--------|
| Stop Sale sync başarı oranı | >95% |
| Ortalama sync süresi | <3 saniye |
| Sedna arayüzünde görünme | 100% |

### Research Reference

📄 `.agent/artifacts/research/2025-12-29-sedna-stopsale-api-analysis.md`

---

## 📋 Requirements

### Functional Requirements

| ID | Requirement |
|----|-------------|
| FR1 | Stop sale kaydı Sedna'ya iki aşamalı olarak gönderilmeli |
| FR2 | Room, Board, Operator ID'leri cache'den alınmalı |
| FR3 | OperatorRemark sonuna virgül eklenmeli |
| FR4 | Sync öncesi CheckStopSaleState ile mevcut durum kontrol edilebilmeli |
| FR5 | Tenant config'de operator_id ve authority_id saklanmalı |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | Cache refresh günlük yapılmalı |
| NFR2 | API timeout 30 saniye |
| NFR3 | Retry logic (3 deneme) |

---

## 📦 Stories

### E3.S1: UpdateStopSale Endpoint Migration

**SP:** 2 | **Priority:** P0

**Description:**
Mevcut `sync_stop_sale()` metodunu `/api/Contract/UpdateStopSale` endpoint'ine geçir.

**Acceptance Criteria:**

- [ ] Endpoint `/api/Contract/UpdateStopSale` olarak değiştirildi
- [ ] HTTP method PUT olarak güncellendi
- [ ] Base request payload yapısı oluşturuldu

**Files to Modify:**

- `apps/api/sedna/service.py`

---

### E3.S2: Two-Phase Save Implementation

**SP:** 3 | **Priority:** P0

**Description:**
Sedna API'sinin gerektirdiği iki aşamalı kayıt sürecini implement et.

**Phase 1:** Boş child array'ler ile ana kayıt oluştur → RecId al
**Phase 2:** RecId ile dolu child array'ler gönder

**Acceptance Criteria:**

- [ ] Phase 1: RecId=0 ile kayıt oluşturulabiliyor
- [ ] Phase 2: Dönen RecId ile child records ekleniyor
- [ ] Her child record'da StopSaleId = ana RecId
- [ ] Hata durumunda rollback yapılıyor

**Technical Details:**

```python
# Phase 1 Request
{
    "RecId": 0,
    "StopSaleRooms": [],
    "StopSaleOperators": [],
    "StopSaleBoards": [],
    "StopSaleMarkets": []
}

# Phase 2 Request
{
    "RecId": 823259,  # Phase 1'den dönen
    "StopSaleRooms": [
        {"RoomTypeId": 63, "State": 1, "StopSaleId": 823259}
    ],
    ...
}
```

**Files to Modify:**

- `apps/api/sedna/service.py`

---

### E3.S3: Reference Data Cache Service

**SP:** 3 | **Priority:** P1

**Description:**
Room Type, Board Type ve Operator listelerini cache'leyen servis oluştur.

**Endpoints to Integrate:**

- `GET /api/Integratiion/GetRoomTypeList?operatorId={id}`
- `GET /api/Service2/GetBoardList`

**Acceptance Criteria:**

- [ ] RoomType cache servisi oluşturuldu
- [ ] BoardType cache servisi oluşturuldu
- [ ] Cache TTL: 24 saat
- [ ] Room code → RoomTypeId lookup çalışıyor
- [ ] Board code → BoardId lookup çalışıyor

**Data Structure:**

```python
class SednaCacheService:
    room_types: dict[str, int]  # {"STDSV": 63, "STDLV": 1364}
    board_types: dict[str, int]  # {"AI": 1, "UAI": 37}
    last_refresh: datetime
    
    async def get_room_type_id(self, code: str) -> int | None
    async def get_board_id(self, code: str) -> int | None
    async def refresh_cache(self, tenant_id: int) -> None
```

**Files to Create:**

- `apps/api/sedna/cache_service.py`

**Files to Modify:**

- `apps/api/main.py` (service initialization)

---

### E3.S4: Tenant Config Extensions

**SP:** 1 | **Priority:** P1

**Description:**
Tenant settings'e Sedna-specific konfigürasyonlar ekle.

**New Config Fields:**

| Field | Type | Description |
|-------|------|-------------|
| sedna_operator_id | integer | Acenta'nın Sedna operator ID'si |
| sedna_operator_code | string | Acenta kodu (örn: "7STAR") |
| sedna_authority_id | integer | Yetki ID'si (varsayılan: 207) |

**Acceptance Criteria:**

- [ ] Tenant settings'de yeni alanlar eklendi
- [ ] Settings sayfasında düzenlenebiliyor
- [ ] sync_stop_sale() bu değerleri kullanıyor

**Files to Modify:**

- `apps/api/tenant/models.py`
- `apps/api/tenant/service.py`
- `apps/web/src/app/settings/page.tsx`

---

### E3.S5: Request Payload Builder

**SP:** 2 | **Priority:** P0

**Description:**
Stop sale verilerinden Sedna API payload'ını oluşturan builder fonksiyonu.

**Responsibilities:**

1. RoomRemark string oluştur (virgülle ayrılmış kodlar)
2. OperatorRemark oluştur (sonuna virgül ekle!)
3. BoardRemark oluştur
4. Child record array'leri oluştur

**Acceptance Criteria:**

- [ ] `_build_stop_sale_payload()` metodu oluşturuldu
- [ ] OperatorRemark sonuna virgül ekleniyor
- [ ] Room codes → StopSaleRooms array dönüşümü
- [ ] Boş room/board durumunda "all" semantiği

**Example:**

```python
def _build_stop_sale_payload(
    self,
    stop_sale: dict,
    hotel_id: int,
    rec_id: int,
    room_type_ids: list[int],
    operator_id: int,
    board_ids: list[int],
) -> dict:
    payload = {
        "RecId": rec_id,
        "HotelId": hotel_id,
        "BeginDate": stop_sale["date_from"].isoformat(),
        "EndDate": stop_sale["date_to"].isoformat(),
        "DeclareDate": datetime.now().isoformat(),
        "Active": 0,
        "RecordUser": "Entegrasyon",
        "RecordSource": 0,
        "StopType": 0 if stop_sale["is_close"] else 1,
        "Authority": self.authority_id,
        "RoomRemark": stop_sale.get("room_type", ""),
        "OperatorRemark": f"{self.operator_code},",  # ⚠️ Virgül!
        "BoardRemark": "",
        "State": 1,
        ...
    }
    return payload
```

**Files to Modify:**

- `apps/api/sedna/service.py`

---

### E3.S6: Integration Testing

**SP:** 2 | **Priority:** P2

**Description:**
test.kodsedna.com ortamında entegrasyon testi.

**Test Scenarios:**

1. Yeni stop sale oluştur
2. Mevcut stop sale güncelle
3. Birden fazla room type ile stop sale
4. Tüm room'lar için stop sale (boş room list)

**Acceptance Criteria:**

- [ ] Test ortamında başarılı kayıt oluşturulabiliyor
- [ ] Sedna arayüzünde kayıtlar görünüyor
- [ ] Child records (room, operator) doğru bağlanmış

**Test Environment:**

```
URL: http://test.kodsedna.com/SednaAgencyB2bApi
Username: 7STAR
Password: 1234
```

---

## 📊 Story Summary

| Story | Title | SP | Priority | Dependencies |
|-------|-------|:--:|:--------:|--------------|
| E3.S1 | UpdateStopSale Endpoint Migration | 2 | P0 | - |
| E3.S2 | Two-Phase Save Implementation | 3 | P0 | E3.S1 |
| E3.S5 | Request Payload Builder | 2 | P0 | E3.S1 |
| E3.S3 | Reference Data Cache Service | 3 | P1 | - |
| E3.S4 | Tenant Config Extensions | 1 | P1 | - |
| E3.S6 | Integration Testing | 2 | P2 | All |
| | **Total** | **13** | | |

---

## 🗓 Implementation Order

```
Week 1 (P0 - Core):
├── E3.S1: UpdateStopSale Endpoint Migration
├── E3.S5: Request Payload Builder
└── E3.S2: Two-Phase Save Implementation

Week 2 (P1 - Support):
├── E3.S3: Reference Data Cache Service
└── E3.S4: Tenant Config Extensions

Week 3 (P2 - Validation):
└── E3.S6: Integration Testing
```

---

## 🔗 Related Documents

| Document | Path |
|----------|------|
| Research Report | `.agent/artifacts/research/2025-12-29-sedna-stopsale-api-analysis.md` |
| Postman Collection | `docs/StopSale.postman_collection.json` |
| Current Implementation | `apps/api/sedna/service.py` |

---

## ⚠️ Technical Risks

| Risk | Mitigation |
|------|-----------|
| Test ortamı farklı davranabilir | Production URL için ayrı config |
| Hotel ID bulunamayabilir | Fuzzy matching + manual mapping |
| Authentication token expire | Session yönetimi ekle |

---

## 📝 Notes

- **OperatorRemark sonuna virgül ekle!** Bu olmadan Sedna arayüzünde görünmeyebilir.
- İlk kayıtta child array'ler **mutlaka boş** olmalı
- Her child record'da `StopSaleId` ana kaydın ID'si olmalı
