# E4: Hotel Fuzzy Match & Selection

**Version:** 1.0  
**Created:** 2025-12-29  
**Status:** Draft  
**Total SP:** 8

---

## 1. Hedefler ve Gerekçe

### Problem

Stop Sale sync işleminde "Hotel not found" hatası alınıyor. Bunun nedenleri:

1. Email'deki otel ismi Sedna'daki isimle birebir eşleşmiyor
2. Kullanıcının oteli manuel olarak eşleştirmesi için bir mekanizma yok
3. Fuzzy matching desteği bulunmuyor

### Çözüm

1. Otel ismi ile fuzzy search yapılarak benzer oteller bulunacak
2. Kullanıcıya en yakın eşleşmeleri sunan modal gösterilecek
3. Kullanıcı doğru oteli seçtikten sonra eşleştirme kaydedilecek
4. Sonraki sync'lerde bu eşleştirme kullanılacak

### Başarı Kriterleri

| Metrik | Hedef |
|--------|-------|
| Hotel match success rate | %95+ |
| Manual selection time | <5 saniye |
| Zero "Hotel not found" errors | Kullanıcı müdahalesi sonrası |

---

## 2. Kullanıcı Senaryoları

### Senaryo 1: Otomatik Eşleşme

```
1. Kullanıcı stop sale email'ini seçip "Sync" tıklar
2. Sistem otel ismini Sedna'da arar
3. Tam eşleşme bulunursa → Sync devam eder ✅
```

### Senaryo 2: Fuzzy Eşleşme ile Öneri

```
1. Kullanıcı stop sale email'ini seçip "Sync" tıklar
2. Sistem otel ismini arar, tam eşleşme BULAMAZ
3. Benzer isimli 5 otel önerilir (modal açılır)
4. Kullanıcı doğru oteli seçer
5. Eşleştirme kaydedilir
6. Sync otomatik tekrar çalışır ✅
```

### Senaryo 3: Hiç Eşleşme Yok

```
1. Sistem otel ismini arar
2. Benzer isim de BULAMAZ (%50 altı benzerlik)
3. "Otel bulunamadı. Manuel olarak Sedna Hotel ID girin" mesajı
4. Kullanıcı ID'yi manuel girer
5. Kayıt oluşturulur
```

---

## 3. Fonksiyonel Gereksinimler

### FR-1: Hotel Search API

| Özellik | Detay |
|---------|-------|
| Endpoint | `GET /api/sedna/hotels/search` |
| Arama Algoritması | Levenshtein distance + token matching |
| Minimum Benzerlik | %50 |
| Maksimum Sonuç | 10 otel |

### FR-2: Hotel Assignment API

| Özellik | Detay |
|---------|-------|
| Endpoint | `POST /api/stop-sales/{id}/assign-hotel` |
| Input | `sedna_hotel_id: int` |
| Side Effect | stop_sales.sedna_hotel_id UPDATE |

### FR-3: Hotel Mapping Cache

| Özellik | Detay |
|---------|-------|
| Tablo | `hotel_mappings` (yeni) |
| Anahtar | `hotel_name_normalized → sedna_hotel_id` |
| TTL | Kalıcı (manuel eşleştirmeler) |

### FR-4: Hotel Selection Modal (Frontend)

| Özellik | Detay |
|---------|-------|
| Trigger | Sync "HOTEL_NOT_FOUND" hatası |
| Gösterilecek | Otel adı, benzerlik %, ülke/şehir |
| Aksiyon | Seç veya Manuel ID Gir |

---

## 4. Non-Functional Gereksinimler

| NFR | Hedef |
|-----|-------|
| Search Response Time | <500ms |
| Modal Load Time | <200ms |
| Hotel List Cache | 24 saat TTL |

---

## 5. Epic Stories

### E4.S1: Hotel Search Service (Backend)

**SP:** 3 | **Priority:** P0

**Acceptance Criteria:**

- [ ] Sedna'dan otel listesi çekilebiliyor
- [ ] Fuzzy search çalışıyor (Levenshtein)
- [ ] Minimum %50 threshold uygulanıyor
- [ ] Sonuçlar benzerlik oranına göre sıralı

**Teknik Notlar:**

```python
# Levenshtein için: python-Levenshtein veya rapidfuzz
# rapidfuzz daha hızlı ve memory-efficient
```

---

### E4.S2: Hotel Assignment Endpoint (Backend)

**SP:** 1 | **Priority:** P0

**Acceptance Criteria:**

- [ ] `POST /api/stop-sales/{id}/assign-hotel` çalışıyor
- [ ] stop_sales.sedna_hotel_id güncelleniyor
- [ ] Başarılı assignment sonrası 200 OK

---

### E4.S3: Hotel Mapping Cache (Backend)

**SP:** 2 | **Priority:** P1

**Acceptance Criteria:**

- [ ] `hotel_mappings` tablosu oluşturuldu
- [ ] İlk eşleştirmede mapping kaydediliyor
- [ ] Sonraki sync'lerde mapping'den lookup yapılıyor

**Tablo Şeması:**

```sql
CREATE TABLE hotel_mappings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    hotel_name_original VARCHAR(255) NOT NULL,
    hotel_name_normalized VARCHAR(255) NOT NULL,
    sedna_hotel_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, hotel_name_normalized)
);
```

---

### E4.S4: Hotel Selection Modal (Frontend)

**SP:** 2 | **Priority:** P0

**Acceptance Criteria:**

- [ ] Modal açılıyor sync hatası sonrası
- [ ] Benzer oteller listeleniyor
- [ ] Tıklama ile seçim yapılabiliyor
- [ ] Seçim sonrası sync otomatik retry

**UI Mockup:**

```
┌─────────────────────────────────────────────┐
│  ⚠️ Otel Bulunamadı                        │
├─────────────────────────────────────────────┤
│  Aranan: "Mandarin Resort"                  │
│                                             │
│  Lütfen doğru oteli seçin:                  │
│                                             │
│  ○ Mandarin Oriental (85% match)            │
│  ○ Mandarin Palace Hotel (72% match)        │
│  ○ Grand Mandarin (68% match)               │
│                                             │
│  ─────────────────────────────              │
│  📝 Manuel Sedna Hotel ID:  [______]        │
│                                             │
│           [İptal]  [Seç ve Sync]            │
└─────────────────────────────────────────────┘
```

---

## 6. Implementation Roadmap

```
Week 1:
├── E4.S1: Hotel Search Service ✓
├── E4.S2: Hotel Assignment Endpoint ✓
└── E4.S3: Hotel Mapping Cache ✓

Week 2:
└── E4.S4: Hotel Selection Modal ✓
```

---

## 7. Teknik Riskler

| Risk | Olasılık | Etki | Mitigasyon |
|------|----------|------|------------|
| Sedna API hotel listesi endpoint yok | Orta | Yüksek | Alternatif endpoint bul veya cache'le |
| Fuzzy match yanlış sonuç | Düşük | Orta | Kullanıcı onayı gerekli |
| Performance (çok otel) | Düşük | Düşük | Cache + pagination |

---

## 8. Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| E3: Stop Sale Integration | Internal | ✅ Complete |
| rapidfuzz library | External | 📦 To install |
| Sedna Hotel API | External | ⚠️ Verify endpoint |
