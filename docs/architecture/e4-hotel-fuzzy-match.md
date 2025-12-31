# E4: Hotel Fuzzy Match & Selection - Architecture

**Version:** 1.0  
**Created:** 2025-12-29  
**Related PRD:** `docs/prd/e4-hotel-fuzzy-match.md`

---

## 1. System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
├─────────────────────────────────────────────────────────────────┤
│  ProcessingPage                                                  │
│  ├── SyncButton                                                  │
│  ├── SyncProgressModal                                           │
│  └── HotelSelectionModal (NEW) ◄──────────────────────────┐     │
│       ├── HotelSearchResults                               │     │
│       └── ManualHotelIdInput                              │     │
└───────────────────────────────────────────────────────────│─────┘
                                                            │
                              ▼                             │
┌─────────────────────────────────────────────────────────────────┐
│                         Backend (FastAPI)                        │
├─────────────────────────────────────────────────────────────────┤
│  routers/                                                        │
│  ├── sync.py                                                     │
│  └── sedna.py ◄───────────────────────────────────────────┐     │
│       ├── GET /hotels/search (NEW)                         │     │
│       └── POST /stop-sales/{id}/assign-hotel (NEW)        │     │
│                                                            │     │
│  sedna/                                                    │     │
│  ├── service.py                                           │     │
│  ├── cache_service.py                                     │     │
│  └── hotel_service.py (NEW) ◄─────────────────────────────┤     │
│       ├── HotelSearchService                              │     │
│       │   ├── search_hotels()                             │     │
│       │   ├── fuzzy_match()                               │     │
│       │   └── normalize_name()                            │     │
│       └── HotelMappingService                             │     │
│           ├── get_mapping()                               │     │
│           └── create_mapping()                            │     │
└───────────────────────────────────────────────────────────│─────┘
                                                            │
                              ▼                             │
┌─────────────────────────────────────────────────────────────────┐
│                         Database (PostgreSQL)                    │
├─────────────────────────────────────────────────────────────────┤
│  Tables:                                                         │
│  ├── stop_sales (existing + sedna_hotel_id column)              │
│  └── hotel_mappings (NEW)                                        │
└─────────────────────────────────────────────────────────────────┘
                                                            
                              ▼                             
┌─────────────────────────────────────────────────────────────────┐
│                    External: Sedna API                           │
├─────────────────────────────────────────────────────────────────┤
│  ? /api/Shop/GetHotels (needs verification)                      │
│  ✓ /api/Contract/UpdateStopSale                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Models

### 2.1 New Table: hotel_mappings

```sql
CREATE TABLE hotel_mappings (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    hotel_name_original VARCHAR(255) NOT NULL,
    hotel_name_normalized VARCHAR(255) NOT NULL,
    sedna_hotel_id INTEGER NOT NULL,
    sedna_hotel_name VARCHAR(255),  -- Sedna'daki gerçek isim
    created_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER REFERENCES users(id),
    
    -- Tenant başına unique mapping
    UNIQUE(tenant_id, hotel_name_normalized)
);

CREATE INDEX idx_hotel_mappings_lookup 
ON hotel_mappings(tenant_id, hotel_name_normalized);
```

### 2.2 Modified Table: stop_sales

```sql
-- Zaten eklendi (v1.6.4)
ALTER TABLE stop_sales 
ADD COLUMN IF NOT EXISTS sedna_hotel_id INTEGER;
```

---

## 3. API Specification

### 3.1 Hotel Search

**Endpoint:** `GET /api/sedna/hotels/search`

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| q | string | ✓ | Aranacak otel adı |
| limit | int | - | Max sonuç (default: 10) |

**Response:**

```json
{
  "query": "Mandarin Resort",
  "query_normalized": "mandarin resort",
  "exact_match": null,
  "suggestions": [
    {
      "id": 18,
      "name": "Mandarin Oriental",
      "similarity": 0.85,
      "location": "Istanbul"
    },
    {
      "id": 42,
      "name": "Mandarin Palace Hotel",
      "similarity": 0.72,
      "location": "Antalya"
    }
  ],
  "cached": true
}
```

**Error Response (404):**

```json
{
  "query": "XYZ Hotel",
  "exact_match": null,
  "suggestions": [],
  "message": "No hotels found matching query"
}
```

### 3.2 Assign Hotel to Stop Sale

**Endpoint:** `POST /api/stop-sales/{stop_sale_id}/assign-hotel`

**Request Body:**

```json
{
  "sedna_hotel_id": 18,
  "save_mapping": true  // Optional: Kaydet ki sonraki sync'lerde kullan
}
```

**Response (200):**

```json
{
  "success": true,
  "stop_sale_id": 2,
  "sedna_hotel_id": 18,
  "hotel_name": "Mandarin Oriental",
  "mapping_saved": true
}
```

---

## 4. Service Layer

### 4.1 HotelSearchService

```python
# apps/api/sedna/hotel_service.py

from rapidfuzz import fuzz, process

class HotelSearchService:
    """
    Hotel search with fuzzy matching.
    
    Uses:
    - Sedna API for hotel list (cached 24h)
    - rapidfuzz for fuzzy string matching
    - Normalizes names for better matching
    """
    
    # Cache
    _hotels_cache: dict[int, list] = {}  # tenant_id -> hotels
    _cache_expiry: dict[int, datetime] = {}
    CACHE_TTL = timedelta(hours=24)
    
    async def search_hotels(
        self,
        query: str,
        tenant_id: int,
        sedna_config: dict,
        limit: int = 10,
    ) -> dict:
        """
        Search hotels by name with fuzzy matching.
        
        Returns:
            {
                "query": original query,
                "exact_match": Hotel or None,
                "suggestions": list of similar hotels with scores
            }
        """
        # 1. Get hotel list (from cache or API)
        hotels = await self._get_hotels(tenant_id, sedna_config)
        
        # 2. Normalize query
        query_normalized = self._normalize_name(query)
        
        # 3. First try exact match
        exact = self._find_exact_match(query_normalized, hotels)
        if exact:
            return {
                "query": query,
                "exact_match": exact,
                "suggestions": []
            }
        
        # 4. Fuzzy match
        suggestions = self._fuzzy_match(query_normalized, hotels, limit)
        
        return {
            "query": query,
            "exact_match": None,
            "suggestions": suggestions
        }
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize hotel name for comparison.
        
        Examples:
        - "Mandarin Resort Hotel & Spa" -> "mandarin resort"
        - "THE MANDARIN PALACE" -> "mandarin palace"
        """
        import re
        
        # Lowercase
        name = name.lower()
        
        # Remove common suffixes
        suffixes = [
            'hotel', 'resort', 'spa', 'suites', 'inn', 
            'palace', 'beach', 'club', 'otel',
            '&', 'and', 'the', '-', "'", '"'
        ]
        for suffix in suffixes:
            name = name.replace(suffix, ' ')
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _fuzzy_match(
        self,
        query: str,
        hotels: list,
        limit: int,
        min_score: int = 50,
    ) -> list[dict]:
        """
        Find similar hotels using rapidfuzz.
        
        Returns hotels with similarity >= min_score, sorted by score.
        """
        hotel_names = {h['RecId']: h['Name'] for h in hotels}
        normalized_names = {
            id: self._normalize_name(name) 
            for id, name in hotel_names.items()
        }
        
        # Find matches
        results = process.extract(
            query,
            normalized_names,
            scorer=fuzz.token_sort_ratio,
            limit=limit,
        )
        
        suggestions = []
        for name, score, hotel_id in results:
            if score >= min_score:
                suggestions.append({
                    "id": hotel_id,
                    "name": hotel_names[hotel_id],
                    "similarity": round(score / 100, 2),
                })
        
        return suggestions
```

### 4.2 HotelMappingService

```python
class HotelMappingService:
    """
    Store and retrieve hotel name -> Sedna ID mappings.
    """
    
    async def get_mapping(
        self,
        tenant_id: int,
        hotel_name: str,
    ) -> Optional[int]:
        """Get Sedna hotel ID from cached mapping."""
        normalized = self._normalize_name(hotel_name)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT sedna_hotel_id FROM hotel_mappings
                WHERE tenant_id = $1 AND hotel_name_normalized = $2
                """,
                tenant_id, normalized,
            )
            return row['sedna_hotel_id'] if row else None
    
    async def create_mapping(
        self,
        tenant_id: int,
        hotel_name_original: str,
        sedna_hotel_id: int,
        sedna_hotel_name: str,
        user_id: int = None,
    ) -> int:
        """Save a new hotel mapping."""
        normalized = self._normalize_name(hotel_name_original)
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO hotel_mappings 
                (tenant_id, hotel_name_original, hotel_name_normalized, 
                 sedna_hotel_id, sedna_hotel_name, created_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (tenant_id, hotel_name_normalized) 
                DO UPDATE SET sedna_hotel_id = EXCLUDED.sedna_hotel_id
                RETURNING id
                """,
                tenant_id, hotel_name_original, normalized,
                sedna_hotel_id, sedna_hotel_name, user_id,
            )
```

---

## 5. Frontend Components

### 5.1 HotelSelectionModal

```tsx
// apps/web/src/components/HotelSelectionModal.tsx

interface HotelSuggestion {
  id: number;
  name: string;
  similarity: number;
  location?: string;
}

interface HotelSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  stopSaleId: number;
  hotelName: string;
  onHotelSelected: (hotelId: number) => void;
}

export function HotelSelectionModal({
  isOpen,
  onClose,
  stopSaleId,
  hotelName,
  onHotelSelected,
}: HotelSelectionModalProps) {
  const [suggestions, setSuggestions] = useState<HotelSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [manualId, setManualId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen && hotelName) {
      searchHotels(hotelName);
    }
  }, [isOpen, hotelName]);

  const searchHotels = async (query: string) => {
    setLoading(true);
    const res = await fetch(
      `${API_URL}/api/sedna/hotels/search?q=${encodeURIComponent(query)}`
    );
    const data = await res.json();
    setSuggestions(data.suggestions || []);
    setLoading(false);
  };

  const handleSubmit = async () => {
    const hotelId = selectedId || parseInt(manualId);
    if (!hotelId) return;

    setSubmitting(true);
    await fetch(`${API_URL}/api/stop-sales/${stopSaleId}/assign-hotel`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ sedna_hotel_id: hotelId, save_mapping: true }),
    });

    onHotelSelected(hotelId);
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>⚠️ Otel Bulunamadı</DialogTitle>
        </DialogHeader>

        <p className="text-sm text-muted-foreground">
          Aranan: <strong>{hotelName}</strong>
        </p>

        {loading ? (
          <LoadingSpinner />
        ) : suggestions.length > 0 ? (
          <>
            <p className="text-sm">Lütfen doğru oteli seçin:</p>
            <RadioGroup value={selectedId} onValueChange={setSelectedId}>
              {suggestions.map((hotel) => (
                <div key={hotel.id} className="flex items-center gap-2">
                  <RadioGroupItem value={hotel.id} id={`hotel-${hotel.id}`} />
                  <Label htmlFor={`hotel-${hotel.id}`}>
                    {hotel.name}
                    <Badge variant="outline" className="ml-2">
                      {Math.round(hotel.similarity * 100)}%
                    </Badge>
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </>
        ) : (
          <p className="text-sm text-yellow-500">Benzer otel bulunamadı.</p>
        )}

        <div className="border-t pt-4 mt-4">
          <Label>Manuel Sedna Hotel ID:</Label>
          <Input
            type="number"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            placeholder="Örn: 18"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            İptal
          </Button>
          <Button 
            onClick={handleSubmit} 
            disabled={!selectedId && !manualId || submitting}
          >
            {submitting ? "Kaydediliyor..." : "Seç ve Sync"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

---

## 6. Sequence Diagram

```
User          Frontend           Backend           Sedna API         DB
 │               │                  │                  │              │
 │──Sync─────────▶                  │                  │              │
 │               │──POST /sync──────▶                  │              │
 │               │                  │──Hotel Search────▶              │
 │               │                  │◀─────────────────│              │
 │               │                  │                  │              │
 │               │                  │ (Hotel Not Found)│              │
 │               │◀─HOTEL_NOT_FOUND─│                  │              │
 │               │                  │                  │              │
 │  Modal Opens  │                  │                  │              │
 │               │──GET /hotels/search?q=Mandarin──────▶              │
 │               │                  │──Get Hotels──────▶              │
 │               │                  │◀─────────────────│              │
 │               │                  │──Fuzzy Match─────│              │
 │               │◀─Suggestions─────│                  │              │
 │               │                  │                  │              │
 │ User Selects  │                  │                  │              │
 │──Select #18───▶                  │                  │              │
 │               │──POST /assign-hotel─────────────────│──────────────▶
 │               │                  │                  │     (UPDATE)
 │               │◀─Success─────────│                  │              │
 │               │                  │                  │              │
 │               │──Retry Sync──────▶                  │              │
 │               │                  │──UpdateStopSale──▶              │
 │               │                  │◀─────────────────│              │
 │               │◀─Success─────────│                  │              │
 │ Sync Complete │                  │                  │              │
```

---

## 7. File Structure

```
apps/api/
├── sedna/
│   ├── service.py           # Modified: use mapping lookup
│   ├── cache_service.py     # Existing
│   └── hotel_service.py     # NEW: HotelSearchService, HotelMappingService
├── routers/
│   └── sedna.py             # NEW: /hotels/search, /stop-sales/.../assign-hotel
└── requirements.txt         # ADD: rapidfuzz

apps/web/
├── src/components/
│   └── HotelSelectionModal.tsx  # NEW
└── src/app/emails/processing/
    └── page.tsx             # Modified: integrate modal
```

---

## 8. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| rapidfuzz | ^3.0.0 | Fast fuzzy string matching (C extension) |

**Installation:**

```bash
pip install rapidfuzz
```

---

## 9. Test Plan

### Unit Tests

| Test | Description |
|------|-------------|
| `test_normalize_name` | "Hotel & Spa" → "hotel spa" |
| `test_fuzzy_match_exact` | 100% match returns first |
| `test_fuzzy_match_partial` | "Mandarin" matches "Mandarin Oriental" |
| `test_fuzzy_match_threshold` | <50% match returns empty |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_search_endpoint` | GET /hotels/search returns suggestions |
| `test_assign_hotel` | POST /assign-hotel updates DB |
| `test_sync_with_mapping` | Sync uses cached mapping |

### E2E Tests

| Test | Description |
|------|-------------|
| `test_hotel_modal_flow` | UI modal opens → select → sync succeeds |
