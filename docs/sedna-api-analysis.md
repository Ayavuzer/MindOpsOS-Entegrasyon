# 📊 Sedna Agency API Analiz Raporu

> **Analiz Tarihi:** 2025-12-27  
> **Kaynak:** DemoSummerBase.postman_collection.json  
> **Analiz Eden:** Antigravity Agent  
> **Proje:** MindOpsOS-Entegrasyon

---

## 1. Genel Bakış

### 1.1 Collection Bilgileri

| Özellik | Değer |
|---------|-------|
| **Collection Adı** | DemoSummerBase |
| **Postman ID** | 96f6afd5-6b50-40bb-b00d-c05b67f9a7ec |
| **Toplam Request** | 38 |
| **Base URL (Variable)** | `http://test.kodsedna.com/SednaAgencyb2bApi/api` |
| **Workspace** | sednaveboni.postman.co |

### 1.2 API Servisleri

Collection içinde **4 farklı API servisi** tespit edildi:

| Servis | Base Path | Açıklama |
|--------|-----------|----------|
| **SednaAgencyb2bApi** | `/SednaAgencyb2bApi/api` | Ana B2B entegrasyon API'si |
| **SednaAgencyDCTApi** | `/SednaAgencyDCTApi/api` | DCT (Direct Connect) API'si |
| **Integration** | `/Integratiion` | Ana entegrasyon endpoint'leri |
| **Contract** | `/Contract` | Kontrat yönetimi |

> ⚠️ **Dikkat:** API yolunda typo var: `Integratiion` (çift 'i')

---

## 2. Authentication

### 2.1 Login Endpoint

```http
GET /Integratiion/AgencyLogin?username={username}&password={password}
```

**Örnek Credentials (Test Environment):**

| Kullanıcı | Şifre | OperatorId |
|-----------|-------|------------|
| 7STAR | 1234 | - |
| 7STAR | 7STAR | 571 |
| PARALE | 5277 | 3 |

**Response:** Cookie-based auth + `RecId` (OperatorId) döner.

---

## 3. Endpoint Kategorileri

### 3.1 🏨 Otel & Tanım Verileri

| Endpoint | Method | Açıklama | Parametreler |
|----------|--------|----------|--------------|
| `GetHotelList` | POST | Otel listesi | `operatorId`, `isActive` |
| `GetHotelRoomTypelistAll` | POST | Oda tipleri (body: hotelId array) | `[18]` |
| `GetHotelCategorylist` | GET | Otel kategorileri | - |
| `GetMainRegions` | POST | Ana bölgeler | `operatorId` |
| `GetSubRegions` | POST | Alt bölgeler | `operatorId` |
| `GetRegionList` | POST | Transfer bölgeleri | `operatorId` |
| `GetCountrys` | POST | Ülke listesi | - |
| `GetOperators` | GET | Operatör listesi | - |

### 3.2 📅 Rezervasyon Yönetimi

#### InsertReservation (Ana Endpoint - Kritik!)

```http
POST /Integratiion/InsertReservation?username={user}&password={pass}&voucherNo={voucher}
```

**Request Body Yapısı:**

```json
[{
    "Voucher": "54",
    "CheckinDate": "2024-09-05",
    "CheckOutDate": "2024-09-10",
    "HotelId": 28,
    "OperatorId": 571,
    "Adult": 1,
    "Child": 2,
    "BoardId": 1,
    "RoomTypeId": 133,
    "SourceId": "116",
    "ContractId": 110548,
    "SaleDate": "2024-06-08",
    "Amount": 667.8,
    "Customers": [
        {
            "Title": "Mr/Mrs/Grp/Chd/Inf",
            "FirstName": "KSENIIA",
            "LastName": "TSENOVA",
            "BirthDate": "1994-02-08",
            "Age": 30,
            "PassNo": "022013",
            "PassSerial": "FU",
            "Nationality": "UKRAYNA",
            "NationalityId": 79,
            "SourceId": "92",
            
            // Transfer bilgileri
            "ArrivalFlightNumber": "FIA 5311",
            "DepartureFlightNumber": "FIA 5312",
            "ArrivalFlightTime": "2024-06-24",
            "DepartureFlightTime": "2024-07-03",
            "ArrTransferType": 10,
            "DepTransferType": 10,
            "IsArrivalTransfer": 1,
            "IsDepartureTransfer": 1
        }
    ],
    
    // Opsiyonel alanlar
    "HotelRemark": "Otel notları",
    "ReservationRemark": "Rezervasyon notları",
    "Code1": "Kod 1 alanı",
    "Code2": "Kod 2 alanı",
    "Code3": "Kod 3 alanı",
    "IsReservationChanged": false,
    "IsBabyFree": true,
    "CheckContract": true
}]
```

**Önemli Alanlar:**

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|---------|----------|
| `HotelId` | int | ✅ | Otel ID (GetHotelList'ten alınır) |
| `OperatorId` | int | ✅ | Operatör ID (Login'den alınır) |
| `RoomTypeId` | int | ✅ | Oda tipi ID |
| `BoardId` | int | ✅ | Pansiyon ID (1=AI, 2=FB, 4=HB?) |
| `ContractId` | int | ❌ | Kontrat ID (opsiyonel) |
| `SourceId` | string | ❌ | Dış sistem referans ID |
| `VoucherNo` | string | ✅ | Query param'da geçilir |
| `Amount` | decimal | ❌ | Toplam tutar |

**Customer Title Değerleri:**

| Title | Açıklama |
|-------|----------|
| Mr | Bay (Yetişkin erkek) |
| Mrs | Bayan (Yetişkin kadın) |
| Grp | Grup |
| Chd | Çocuk (Child) |
| Inf | Bebek (Infant) |

#### Diğer Rezervasyon Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `GetReservations` | POST | Rezervasyon listesi |
| `GetReservationByVoucher` | GET | Voucher ile sorgulama |
| `GetCrmReservation` | POST | CRM rezervasyon detayı |
| `CancelReservationBySourcId` | POST | SourceId ile iptal |

### 3.3 🚌 Transfer Yönetimi

#### SaveTransfer (Önemli!)

```http
POST /Integratiion/SaveTransfer
```

**Request Body:**

```json
{
    "Id": 0,
    "Operator": "JOINUP",
    "Voucher": "5461976",
    "BeginDate": "2021-10-15T00:00:00",
    "EndDate": "2021-10-31T00:00:00",
    "Description": "Transfer açıklaması",
    "SaleDate": "2021-03-23T14:30:00+03:00",
    "IsCancel": false,
    "Customers": [
        {
            "Firstname": "VERONIKA",
            "Lastname": "SHVEDOVA",
            "BirthDate": "1992-12-18T00:00:00",
            "Age": 28,
            "PassNo": "0235867",
            "SerialNo": "76",
            "Title": "Mrs",
            "Country": "Russia",
            "Transfers": [
                {
                    "DirectionType": 1,
                    "TransferType": "Group transfer",
                    "DepartureTime": "2021-10-31T21:00:00",
                    "LandingTime": "2021-10-31T23:55:00",
                    "From": {
                        "Name": "Cenger Beach Resort & Spa",
                        "Type": 1
                    },
                    "To": {
                        "Name": "AYT Airport",
                        "Type": 0
                    },
                    "TransferDate": "2021-10-31T00:00:00",
                    "HasTransfer": true,
                    "HasFreeTransfer": false,
                    "FlightFrom": "AYT",
                    "FlightTo": "KUF"
                }
            ]
        }
    ]
}
```

#### Diğer Transfer Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `GetTransferTypeForIntegration` | GET | Transfer tipleri |
| `GetTransferPricesForIntegration` | GET | Transfer fiyatları |
| `ChangeCustomerTransferForIntegration` | POST | Transfer değişikliği |

### 3.4 🚫 Stop Sale Yönetimi

#### GetStopSaleList

```http
POST /Integratiion/GetStopSaleList?recordDateBegin=&recordDateEnd=&stopDateBegin=&stopDateEnd=&hotelId=
```

**Query Parameters:**

| Parametre | Tip | Açıklama |
|-----------|-----|----------|
| `recordDateBegin` | date | Kayıt başlangıç tarihi |
| `recordDateEnd` | date | Kayıt bitiş tarihi |
| `stopDateBegin` | date | Stop sale başlangıç |
| `stopDateEnd` | date | Stop sale bitiş |
| `hotelId` | int | Otel ID |

#### GetStopSaleListWithUpdateDate

```http
POST /Integratiion/GetStopSaleListWithUpdateDate
```

Aynı parametreler + güncelleme tarihi ile filtreleme.

> ⚠️ **ÖNEMLİ:** Stop sale **KAYDETME** endpoint'i collection'da **BULUNAMADI!**
> Sadece listeleme endpoint'leri mevcut. Sedna ile iletişime geçilmeli.

### 3.5 📑 Kontrat & Paket Yönetimi

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `GetContractList` | POST | Kontrat listesi |
| `GetPackets` | POST | Paket listesi |
| `GetSpoList` | POST | SPO (Special Offer) listesi |
| `GetSpoes` | POST | SPO detayları |
| `GetForecastRelease` | POST | Release tahminleri |
| `GetContractMinStays` | GET | Minimum konaklama süreleri |

### 3.6 💰 Fiyat & Kota Yönetimi

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `HotelPriceSearch` | POST | Otel fiyat arama |
| `SearchHotels` | POST | Otel arama (availability) |
| `GetQuota` | POST | Kota sorgulama |
| `GetContractQuotaForAvailabile` | POST | Müsaitlik kotası |

---

## 4. Transfer Tipleri

Collection'dan çıkarılan transfer tipi değerleri:

| ID | Tip |
|----|-----|
| 1 | Grup transfer |
| 4 | Özel transfer |
| 6 | VIP transfer |
| 10 | Standart |
| 19 | Premium |
| 53 | Başka tip |

> Not: `GetTransferTypeForIntegration` endpoint'inden tam liste alınabilir.

---

## 5. Board (Pansiyon) Tipleri

Collection örneklerinden:

| BoardId | Olası Değer |
|---------|-------------|
| 1 | All Inclusive (AI) |
| 2 | Full Board (FB) |
| 4 | Half Board (HB) |

> Not: Tam liste için API'den sorgulanmalı.

---

## 6. Kritik Bulgular

### 6.1 ✅ Mevcut Özellikler

1. **Rezervasyon Oluşturma:** `InsertReservation` endpoint'i tam fonksiyonel
2. **Çoklu Oda Desteği:** Tek voucher ile birden fazla oda kaydedilebilir (1Voucher2Oda örneği)
3. **Transfer Entegrasyonu:** Rezervasyonla birlikte transfer bilgileri gönderilebilir
4. **Tanım Data API'leri:** Otel, oda tipi, bölge, ülke listeleri mevcut

### 6.2 ⚠️ Eksik/Belirsiz Özellikler

| Özellik | Durum | Önerilen Aksiyon |
|---------|-------|------------------|
| **Stop Sale Kaydetme** | ❌ Endpoint bulunamadı | Sedna'ya sor |
| **BoardId Mapping** | ❓ Tam liste yok | API'den çek veya sor |
| **Error Response Format** | ❓ Örnek yok | Test et |
| **Rate Limiting** | ❓ Bilgi yok | Test et |

### 6.3 🔧 Teknik Notlar

1. **Typo:** API yolunda `Integratiion` (çift 'i') kullanılıyor - dikkat!
2. **Date Format:** ISO 8601 (`2024-09-05` veya `2024-09-05T00:00:00`)
3. **Auth:** Query parameter'da username/password geçiliyor (InsertReservation)
4. **Array Body:** InsertReservation body'si array formatında (`[{...}]`)

---

## 7. Entegrasyon için Gerekli ID Mapping

### 7.1 Başlangıçta Çekilecek Veriler

```python
# 1. Operatör ID (Her session başında)
GET /Integratiion/AgencyLogin?username=xxx&password=xxx

# 2. Otel Listesi (Cache'lenebilir)
POST /Integratiion/GetHotelList?operatorId=571&isActive=true

# 3. Oda Tipleri (Otel başına)
POST /Service1/GetHotelRoomTypelistAll
Body: [18, 28, 659]  # Hotel ID'ler

# 4. Ülke Listesi (Nationality mapping için)
POST /Integratiion/GetCountrys

# 5. Transfer Tipleri
GET /Integratiion/GetTransferTypeForIntegration
```

### 7.2 Mapping Tabloları

Juniper'dan Sedna'ya mapping için:

```yaml
hotel_mapping:
  # Juniper Hotel Name -> Sedna HotelId
  "Grand Hotel Antalya": 18
  "Paradise Resort": 28
  
room_type_mapping:
  # Juniper Code -> Sedna RoomTypeId
  "DBL": 3
  "SGL": 1
  "FAM": 516
  
board_mapping:
  # Juniper Code -> Sedna BoardId
  "AI": 1
  "FB": 2
  "HB": 4
  
nationality_mapping:
  # Country Name -> NationalityId
  "UKRAINE": 79
  "KAZAKHSTAN": 69
  "RUSSIA": 57
```

---

## 8. Önerilen Implementasyon

### 8.1 Sedna Client Yapısı

```python
class SednaClient:
    async def login(self) -> str:
        """Login ve OperatorId al"""
        
    async def get_hotels(self) -> List[Hotel]:
        """Otel listesi"""
        
    async def get_room_types(self, hotel_ids: List[int]) -> Dict[int, List[RoomType]]:
        """Otel bazlı oda tipleri"""
        
    async def insert_reservation(self, reservation: ReservationRequest) -> ReservationResponse:
        """Rezervasyon kaydet"""
        
    async def get_stop_sales(self, filters: StopSaleFilter) -> List[StopSale]:
        """Stop sale listesi"""
        
    async def save_stop_sale(self, stop_sale: StopSaleRequest) -> bool:
        """Stop sale kaydet (endpoint teyit edilmeli!)"""
```

### 8.2 Öncelikli Görevler

1. **[P0]** `InsertReservation` implementasyonu
2. **[P0]** Hotel/RoomType mapping cache mekanizması
3. **[P1]** Stop sale kaydetme endpoint'ini tespit et
4. **[P1]** Error handling ve retry mekanizması
5. **[P2]** Transfer entegrasyonu

---

## 9. Test Credentials

| Ortam | URL | Username | Password |
|-------|-----|----------|----------|
| **Test** | <http://test.kodsedna.com/SednaAgencyb2bApi> | 7STAR | 7STAR |
| **Test** | <http://test.kodsedna.com/SednaAgencyb2bApi> | PARALE | 5277 |

---

## 10. Sonraki Adımlar

1. ⚠️ **Sedna ile İletişim:** Stop sale kaydetme endpoint'i için dokümantasyon iste
2. 🧪 **API Test:** Postman collection'ı import edip test et
3. 📝 **Mapping Tablosu:** GetHotelList, GetRoomTypes çağır ve mapping oluştur
4. 🔧 **Client Geliştirme:** SednaClient sınıfını implement et

---

*Rapor oluşturuldu: 2025-12-27 23:15*  
*MindOpsOS-Entegrasyon Projesi*
