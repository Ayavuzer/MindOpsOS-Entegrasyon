# E3: Sedna Stop Sales - Architecture

> **Epic:** E3 - Sedna Stop Sales Tam Entegrasyonu
> **Created:** 2025-12-29

---

## 🏗 System Architecture

### Current State

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CURRENT FLOW (Broken)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Email → Parser → stop_sales table → sync_stop_sale()               │
│                                           │                          │
│                                           ▼                          │
│                    ❌ /api/StopSale/InsertStopSale                   │
│                       (Wrong endpoint, missing fields)               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Target State

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TARGET FLOW (Two-Phase)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Email → Parser → stop_sales table → sync_stop_sale()               │
│                                           │                          │
│                          ┌────────────────┴────────────────┐        │
│                          ▼                                  ▼        │
│                   SednaCacheService              TenantConfig        │
│                   ├─ RoomTypes                   ├─ operator_id      │
│                   └─ BoardTypes                  └─ authority_id     │
│                          │                                  │        │
│                          └────────────────┬────────────────┘        │
│                                           ▼                          │
│                              PayloadBuilder                          │
│                                           │                          │
│                    ┌──────────────────────┴───────────────────┐     │
│                    ▼                                          ▼     │
│              PHASE 1                                    PHASE 2     │
│         PUT UpdateStopSale                         PUT UpdateStopSale
│         (RecId=0, empty[])                         (RecId=N, filled[])
│                    │                                          │     │
│                    └─────────── returns RecId ───────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 New Components

### 1. SednaCacheService

```python
# apps/api/sedna/cache_service.py

from datetime import datetime, timedelta
from typing import Optional
import httpx
import asyncpg

class SednaCacheService:
    """
    Cache service for Sedna reference data.
    Reduces API calls by caching Room/Board types locally.
    """
    
    CACHE_TTL = timedelta(hours=24)
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self._room_types: dict[int, dict[str, int]] = {}  # tenant_id -> {code: id}
        self._board_types: dict[str, int] = {}             # Global
        self._last_refresh: Optional[datetime] = None
    
    async def get_room_type_id(
        self, 
        tenant_id: int, 
        code: str,
        sedna_config: dict
    ) -> Optional[int]:
        """
        Get Sedna RoomTypeId from room code.
        
        Args:
            tenant_id: Tenant ID
            code: Room type code (e.g., "STDSV")
            sedna_config: Sedna API config
            
        Returns:
            RoomTypeId or None if not found
        """
        if self._should_refresh():
            await self.refresh_room_types(tenant_id, sedna_config)
        
        return self._room_types.get(tenant_id, {}).get(code.upper())
    
    async def get_board_id(self, code: str, sedna_config: dict) -> Optional[int]:
        """Get Sedna BoardId from board code."""
        if not self._board_types:
            await self.refresh_board_types(sedna_config)
        
        return self._board_types.get(code.upper())
    
    async def refresh_room_types(
        self, 
        tenant_id: int, 
        sedna_config: dict
    ) -> None:
        """Fetch room types from Sedna API."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{sedna_config['api_url']}/api/Integratiion/GetRoomTypeList",
                params={"operatorId": sedna_config["operator_id"]}
            )
            
            if response.status_code == 200:
                data = response.json()
                self._room_types[tenant_id] = {
                    item["Code"].upper(): item["RoomTypeId"]
                    for item in data.get("Data", [])
                }
    
    async def refresh_board_types(self, sedna_config: dict) -> None:
        """Fetch board types from Sedna API."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{sedna_config['api_url']}/api/Service2/GetBoardList"
            )
            
            if response.status_code == 200:
                data = response.json()
                self._board_types = {
                    item["Code"].upper(): item["BoardId"]
                    for item in data.get("Data", [])
                }
        
        self._last_refresh = datetime.now()
    
    def _should_refresh(self) -> bool:
        """Check if cache needs refresh."""
        if not self._last_refresh:
            return True
        return datetime.now() - self._last_refresh > self.CACHE_TTL
```

### 2. Updated TenantSednaService

```python
# apps/api/sedna/service.py - Updated sync_stop_sale()

async def sync_stop_sale(
    self,
    tenant_id: int,
    stop_sale_id: int,
) -> SyncResult:
    """
    Sync a stop sale to Sedna using two-phase save.
    
    Phase 1: Create main record with empty child arrays
    Phase 2: Update with filled child arrays using returned RecId
    """
    # Get configs
    sedna_config = await self._get_sedna_config(tenant_id)
    if not sedna_config:
        return SyncResult(success=False, message="Sedna not configured")
    
    # Get stop sale data
    async with self.pool.acquire() as conn:
        stop_sale = await conn.fetchrow(
            "SELECT * FROM stop_sales WHERE id = $1 AND tenant_id = $2",
            stop_sale_id, tenant_id
        )
        
        if not stop_sale:
            return SyncResult(success=False, message="Stop sale not found")
        
        if stop_sale["sedna_synced"]:
            return SyncResult(success=True, message="Already synced")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Lookup hotel ID
            hotel_id = await self._find_hotel_id(
                client, sedna_config, stop_sale["hotel_name"]
            )
            if not hotel_id:
                return SyncResult(
                    success=False, 
                    message=f"Hotel not found: {stop_sale['hotel_name']}"
                )
            
            # Lookup room type IDs
            room_type_ids = []
            if stop_sale.get("room_type"):
                for code in stop_sale["room_type"].split(","):
                    code = code.strip()
                    if code:
                        rt_id = await self.cache_service.get_room_type_id(
                            tenant_id, code, sedna_config
                        )
                        if rt_id:
                            room_type_ids.append(rt_id)
            
            # ============================================
            # PHASE 1: Create main record (empty children)
            # ============================================
            phase1_payload = self._build_stop_sale_payload(
                stop_sale=stop_sale,
                hotel_id=hotel_id,
                rec_id=0,  # New record
                room_type_ids=[],  # Empty!
                operator_id=sedna_config["operator_id"],
                operator_code=sedna_config["operator_code"],
                authority_id=sedna_config.get("authority_id", 207),
            )
            
            response1 = await client.put(
                f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
                json=phase1_payload,
            )
            
            if response1.status_code != 200:
                return SyncResult(
                    success=False, 
                    message=f"Phase 1 failed: HTTP {response1.status_code}"
                )
            
            data1 = response1.json()
            if data1.get("ErrorType") != 0:
                return SyncResult(
                    success=False, 
                    message=f"Phase 1 error: {data1.get('Message')}"
                )
            
            rec_id = data1.get("RecId")
            if not rec_id:
                return SyncResult(
                    success=False, 
                    message="Phase 1 did not return RecId"
                )
            
            # ============================================
            # PHASE 2: Update with filled children
            # ============================================
            phase2_payload = self._build_stop_sale_payload(
                stop_sale=stop_sale,
                hotel_id=hotel_id,
                rec_id=rec_id,  # Use returned ID
                room_type_ids=room_type_ids,  # Now filled
                operator_id=sedna_config["operator_id"],
                operator_code=sedna_config["operator_code"],
                authority_id=sedna_config.get("authority_id", 207),
            )
            
            response2 = await client.put(
                f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
                json=phase2_payload,
            )
            
            if response2.status_code != 200:
                return SyncResult(
                    success=False, 
                    message=f"Phase 2 failed: HTTP {response2.status_code}"
                )
            
            data2 = response2.json()
            if data2.get("ErrorType") != 0:
                return SyncResult(
                    success=False, 
                    message=f"Phase 2 error: {data2.get('Message')}"
                )
            
            # Update local DB
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE stop_sales 
                    SET sedna_synced = true, 
                        sedna_rec_id = $1,
                        sedna_sync_at = NOW(),
                        status = 'synced'
                    WHERE id = $2 AND tenant_id = $3
                    """,
                    rec_id, stop_sale_id, tenant_id
                )
            
            return SyncResult(
                success=True,
                message="Synced successfully (two-phase)",
                sedna_rec_id=rec_id,
            )
            
    except Exception as e:
        return SyncResult(success=False, message=str(e))


def _build_stop_sale_payload(
    self,
    stop_sale: dict,
    hotel_id: int,
    rec_id: int,
    room_type_ids: list[int],
    operator_id: int,
    operator_code: str,
    authority_id: int = 207,
) -> dict:
    """
    Build Sedna UpdateStopSale request payload.
    
    IMPORTANT: 
    - OperatorRemark must end with comma!
    - For Phase 1, pass empty room_type_ids
    - For Phase 2, pass filled room_type_ids with rec_id set
    """
    from datetime import datetime
    
    # Build child arrays (empty for Phase 1, filled for Phase 2)
    stop_sale_rooms = []
    stop_sale_operators = []
    
    if rec_id > 0:  # Phase 2: Fill with data
        stop_sale_rooms = [
            {"RoomTypeId": rt_id, "State": 1, "StopSaleId": rec_id}
            for rt_id in room_type_ids
        ]
        stop_sale_operators = [
            {"OperatorId": operator_id, "State": 1, "StopSaleId": rec_id}
        ]
    
    return {
        "RecId": rec_id,
        "HotelId": hotel_id,
        "BeginDate": stop_sale["date_from"].isoformat() + "T00:00:00",
        "EndDate": stop_sale["date_to"].isoformat() + "T00:00:00",
        "DeclareDate": datetime.now().isoformat(),
        "Active": 0,
        "RecordUser": "Entegrasyon",
        "RecordSource": 0,
        "StopType": 0 if stop_sale.get("is_close", True) else 1,
        "Authority": authority_id,
        "RoomRemark": stop_sale.get("room_type", "") or "",
        "OperatorRemark": f"{operator_code},",  # ⚠️ Virgül zorunlu!
        "BoardRemark": "",
        "State": 1,
        "StopSaleRooms": stop_sale_rooms,
        "StopSaleOperators": stop_sale_operators,
        "StopSaleBoards": [],  # TODO: Add board support
        "StopSaleMarkets": [],
    }
```

---

## 🗄 Database Changes

### Tenant Settings Extensions

```sql
-- Add Sedna-specific config fields to tenant_settings
ALTER TABLE tenant_settings 
ADD COLUMN IF NOT EXISTS sedna_operator_id INTEGER,
ADD COLUMN IF NOT EXISTS sedna_operator_code VARCHAR(50),
ADD COLUMN IF NOT EXISTS sedna_authority_id INTEGER DEFAULT 207;

COMMENT ON COLUMN tenant_settings.sedna_operator_id IS 'Sedna operator/agency ID';
COMMENT ON COLUMN tenant_settings.sedna_operator_code IS 'Sedna operator code (e.g., 7STAR)';
COMMENT ON COLUMN tenant_settings.sedna_authority_id IS 'Sedna authority ID for stop sales';
```

### Stop Sales Table (Existing)

No changes needed. Current fields are sufficient:

- `sedna_synced` (boolean)
- `sedna_rec_id` (integer) - Will store the RecId from Sedna
- `sedna_sync_at` (timestamp)

---

## 🔌 API Endpoints

### Sedna External API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/Contract/UpdateStopSale` | PUT | Main stop sale CRUD |
| `/api/Contract/CheckStopSaleState` | POST | Check existing state |
| `/api/Integratiion/GetRoomTypeList` | POST | Room type lookup |
| `/api/Service2/GetBoardList` | GET | Board type lookup |

### Internal API (No changes)

Existing `/api/sync/emails` endpoint will use updated `sync_stop_sale()`.

---

## 📊 Sequence Diagram

```
┌────────┐     ┌─────────────┐     ┌──────────────┐     ┌───────────┐
│ Client │     │ SyncService │     │ CacheService │     │ Sedna API │
└───┬────┘     └──────┬──────┘     └──────┬───────┘     └─────┬─────┘
    │                 │                   │                   │
    │  Sync StopSale  │                   │                   │
    │────────────────>│                   │                   │
    │                 │                   │                   │
    │                 │  Get RoomTypeIds  │                   │
    │                 │──────────────────>│                   │
    │                 │                   │                   │
    │                 │<──────────────────│                   │
    │                 │   {STDSV: 63}     │                   │
    │                 │                   │                   │
    │                 │        PHASE 1: Create (RecId=0)      │
    │                 │───────────────────────────────────────>│
    │                 │                   │                   │
    │                 │<───────────────────────────────────────│
    │                 │           {RecId: 823259}             │
    │                 │                   │                   │
    │                 │        PHASE 2: Update (RecId=823259) │
    │                 │───────────────────────────────────────>│
    │                 │                   │                   │
    │                 │<───────────────────────────────────────│
    │                 │              {Success}                │
    │                 │                   │                   │
    │                 │  Update DB        │                   │
    │                 │  sedna_synced=T   │                   │
    │                 │  sedna_rec_id=823259                  │
    │                 │                   │                   │
    │<────────────────│                   │                   │
    │   SyncResult    │                   │                   │
    │                 │                   │                   │
```

---

## 🗂 File Structure

```
apps/api/sedna/
├── __init__.py
├── service.py          # TenantSednaService (updated)
├── cache_service.py    # SednaCacheService (new)
├── bulk_sync_service.py
└── report_service.py
```

---

## ⚙️ Configuration

### Environment Variables

No new environment variables needed. All config stored per-tenant in database.

### Tenant Settings (UI)

New fields in Settings page:

- `Sedna Operator ID` (required)
- `Sedna Operator Code` (required)
- `Sedna Authority ID` (optional, default: 207)

---

## 🧪 Test Plan

### Unit Tests

```python
# tests/test_sedna_stopsale.py

@pytest.mark.asyncio
async def test_build_phase1_payload():
    """Phase 1 payload should have empty child arrays."""
    payload = service._build_stop_sale_payload(
        stop_sale={"date_from": date.today(), ...},
        rec_id=0,
        room_type_ids=[],  # Empty for Phase 1
        ...
    )
    assert payload["RecId"] == 0
    assert payload["StopSaleRooms"] == []
    assert payload["StopSaleOperators"] == []

@pytest.mark.asyncio
async def test_build_phase2_payload():
    """Phase 2 payload should have filled child arrays with StopSaleId."""
    payload = service._build_stop_sale_payload(
        stop_sale={"date_from": date.today(), ...},
        rec_id=823259,
        room_type_ids=[63, 1364],
        ...
    )
    assert payload["RecId"] == 823259
    assert len(payload["StopSaleRooms"]) == 2
    assert payload["StopSaleRooms"][0]["StopSaleId"] == 823259

@pytest.mark.asyncio
async def test_operator_remark_ends_with_comma():
    """OperatorRemark must end with comma."""
    payload = service._build_stop_sale_payload(
        ...,
        operator_code="7STAR",
    )
    assert payload["OperatorRemark"] == "7STAR,"
```

### Integration Tests

```bash
# Against test.kodsedna.com
API_URL=http://test.kodsedna.com/SednaAgencyB2bApi
USERNAME=7STAR
PASSWORD=1234

# 1. Create stop sale
# 2. Verify in Sedna UI
# 3. Check child records linked correctly
```

---

## 📝 Migration Plan

1. **Deploy cache_service.py** - No impact
2. **Update tenant settings schema** - Add new columns
3. **Configure test tenant** - Add operator_id/code
4. **Deploy updated service.py** - Replace sync logic
5. **Test with single stop sale** - Verify two-phase works
6. **Enable for all tenants** - Full rollout
