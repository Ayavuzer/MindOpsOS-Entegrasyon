"""Tenant-aware Sedna sync service."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import httpx
import asyncpg

from tenant.service import TenantSettingsService

if TYPE_CHECKING:
    from sedna.cache_service import SednaCacheService


@dataclass
class SyncResult:
    """Result of sync operation."""
    
    success: bool
    message: str
    sedna_rec_id: Optional[int] = None
    details: dict = field(default_factory=dict)


class TenantSednaService:
    """Tenant-aware Sedna sync service."""
    
    def __init__(
        self, 
        pool: asyncpg.Pool, 
        settings_service: TenantSettingsService,
        cache_service: "SednaCacheService" = None,
    ):
        self.pool = pool
        self.settings_service = settings_service
        self.cache_service = cache_service
    
    async def _get_sedna_config(self, tenant_id: int) -> Optional[dict]:
        """Get Sedna config with decrypted password."""
        credentials = await self.settings_service.get_decrypted_credentials(tenant_id)
        if not credentials:
            return None
        
        sedna = credentials.get("sedna", {})
        if not sedna.get("api_url") or not sedna.get("username"):
            return None
        
        # Also get operator_id from tenant_settings
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT sedna_operator_id FROM tenant_settings WHERE tenant_id = $1",
                tenant_id,
            )
            if row and row["sedna_operator_id"]:
                sedna["operator_id"] = row["sedna_operator_id"]
        
        return sedna
    
    async def sync_reservation(
        self,
        tenant_id: int,
        email_id: int,
    ) -> SyncResult:
        """
        Sync a reservation to Sedna.
        
        Args:
            tenant_id: Tenant ID
            email_id: Source email ID containing reservation data
            
        Returns:
            SyncResult
        """
        # Get Sedna config
        sedna_config = await self._get_sedna_config(tenant_id)
        if not sedna_config:
            return SyncResult(
                success=False,
                message="Sedna not configured",
            )
        
        # Get reservation data from database
        async with self.pool.acquire() as conn:
            reservation = await conn.fetchrow(
                """
                SELECT * FROM reservations 
                WHERE source_email_id = $1 AND tenant_id = $2
                """,
                email_id,
                tenant_id,
            )
            
            if not reservation:
                return SyncResult(
                    success=False,
                    message="Reservation not found",
                )
            
            if reservation["sedna_synced"]:
                return SyncResult(
                    success=True,
                    message="Already synced",
                    sedna_rec_id=reservation.get("sedna_rec_id"),
                )
        
        # Build Sedna API request
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First, we need hotel_id - search by hotel name
                hotel_id = await self._find_hotel_id(
                    client, 
                    sedna_config, 
                    reservation["hotel_name"]
                )
                
                if not hotel_id:
                    return SyncResult(
                        success=False,
                        message=f"Hotel not found in Sedna: {reservation['hotel_name']}",
                    )
                
                # Create reservation in Sedna
                response = await client.post(
                    f"{sedna_config['api_url']}/api/Reservation/InsertReservation",
                    json={
                        "HotelId": hotel_id,
                        "OperatorId": sedna_config.get("operator_id", 0),
                        "CheckinDate": reservation["check_in"].strftime("%Y-%m-%d"),
                        "CheckOutDate": reservation["check_out"].strftime("%Y-%m-%d"),
                        "Adult": reservation["adults"],
                        "Child": reservation["children"] or 0,
                        "BoardId": 1,  # TODO: Map board type
                        "RoomTypeId": 1,  # TODO: Map room type
                        "TotalPrice": float(reservation["total_price"]) if reservation["total_price"] else 0,
                        "Currency": reservation["currency"] or "EUR",
                        "VoucherNo": reservation["voucher_no"],
                        "SourceId": f"MO-{reservation['id']}",
                        "Customers": reservation.get("guests", [])[:1] if reservation.get("guests") else [],
                    },
                    params={
                        "username": sedna_config["username"],
                        "password": sedna_config["password"],
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ErrorType") == 0 and data.get("RecId"):
                        # Update reservation with Sedna RecId
                        async with self.pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE reservations 
                                SET sedna_synced = true, sedna_rec_id = $1
                                WHERE id = $2 AND tenant_id = $3
                                """,
                                data["RecId"],
                                reservation["id"],
                                tenant_id,
                            )
                        
                        return SyncResult(
                            success=True,
                            message="Synced successfully",
                            sedna_rec_id=data["RecId"],
                        )
                    else:
                        return SyncResult(
                            success=False,
                            message=data.get("Message", "Sedna API error"),
                            details=data,
                        )
                else:
                    return SyncResult(
                        success=False,
                        message=f"HTTP {response.status_code}",
                    )
                    
        except Exception as e:
            return SyncResult(
                success=False,
                message=str(e),
            )
    
    async def sync_stop_sale(
        self,
        tenant_id: int,
        stop_sale_id: int,
    ) -> SyncResult:
        """
        Sync a stop sale to Sedna using two-phase save.
        
        Phase 1: Create main record with empty child arrays (RecId=0)
        Phase 2: Update with filled child arrays using returned RecId
        
        Args:
            tenant_id: Tenant ID
            stop_sale_id: Stop sale record ID
            
        Returns:
            SyncResult
        """
        # Get Sedna config
        sedna_config = await self._get_sedna_config(tenant_id)
        if not sedna_config:
            return SyncResult(
                success=False,
                message="Sedna not configured",
            )
        
        # Get stop sale data
        async with self.pool.acquire() as conn:
            stop_sale = await conn.fetchrow(
                "SELECT * FROM stop_sales WHERE id = $1 AND tenant_id = $2",
                stop_sale_id,
                tenant_id,
            )
            
            if not stop_sale:
                return SyncResult(
                    success=False,
                    message="Stop sale not found",
                )
            
            if stop_sale.get("sedna_synced"):
                return SyncResult(
                    success=True,
                    message="Already synced",
                )
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First check if hotel ID is pre-configured
                hotel_id = stop_sale.get("sedna_hotel_id")
                
                # If not, try to find by name
                if not hotel_id:
                    hotel_id = await self._find_hotel_id(
                        client,
                        sedna_config,
                        stop_sale["hotel_name"]
                    )
                
                if not hotel_id:
                    return SyncResult(
                        success=False,
                        message=f"Hotel not found: {stop_sale['hotel_name']}",
                    )
                
                # Get operator settings (use defaults if not configured)
                operator_id = sedna_config.get("operator_id", 571)
                operator_code = sedna_config.get("operator_code", "7STAR")
                authority_id = sedna_config.get("authority_id", 207)
                
                # Parse room types from room_type string using cache service
                room_type_ids = []
                room_type_str = stop_sale.get("room_type") or ""
                if room_type_str and self.cache_service:
                    room_codes = [c.strip() for c in room_type_str.split(",") if c.strip()]
                    room_type_ids = await self.cache_service.get_room_type_ids(
                        tenant_id, room_codes, sedna_config
                    )
                
                # ==============================================
                # PHASE 1: Create main record (empty children)
                # ==============================================
                phase1_payload = self._build_stop_sale_payload(
                    stop_sale=dict(stop_sale),
                    hotel_id=hotel_id,
                    rec_id=0,  # New record
                    room_type_ids=[],  # Empty for Phase 1!
                    operator_id=operator_id,
                    operator_code=operator_code,
                    authority_id=authority_id,
                )
                
                response1 = await client.put(
                    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
                    json=phase1_payload,
                    params={
                        "username": sedna_config["username"],
                        "password": sedna_config["password"],
                    },
                )
                
                if response1.status_code != 200:
                    return SyncResult(
                        success=False,
                        message=f"Phase 1 failed: HTTP {response1.status_code}",
                    )
                
                data1 = response1.json()
                if data1.get("ErrorType") != 0:
                    return SyncResult(
                        success=False,
                        message=f"Phase 1 error: {data1.get('Message', 'Unknown error')}",
                    )
                
                rec_id = data1.get("RecId")
                if not rec_id:
                    return SyncResult(
                        success=False,
                        message="Phase 1 did not return RecId",
                    )
                
                # ==============================================
                # PHASE 2: Update with filled children
                # ==============================================
                phase2_payload = self._build_stop_sale_payload(
                    stop_sale=dict(stop_sale),
                    hotel_id=hotel_id,
                    rec_id=rec_id,  # Use returned ID
                    room_type_ids=room_type_ids,  # Now we can fill if we have IDs
                    operator_id=operator_id,
                    operator_code=operator_code,
                    authority_id=authority_id,
                )
                
                response2 = await client.put(
                    f"{sedna_config['api_url']}/api/Contract/UpdateStopSale",
                    json=phase2_payload,
                    params={
                        "username": sedna_config["username"],
                        "password": sedna_config["password"],
                    },
                )
                
                if response2.status_code != 200:
                    return SyncResult(
                        success=False,
                        message=f"Phase 2 failed: HTTP {response2.status_code}",
                    )
                
                data2 = response2.json()
                if data2.get("ErrorType") != 0:
                    return SyncResult(
                        success=False,
                        message=f"Phase 2 error: {data2.get('Message', 'Unknown error')}",
                    )
                
                # Update local database
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
                        rec_id,
                        stop_sale_id,
                        tenant_id,
                    )
                
                return SyncResult(
                    success=True,
                    message="Synced successfully (two-phase)",
                    sedna_rec_id=rec_id,
                )
                    
        except Exception as e:
            return SyncResult(
                success=False,
                message=str(e),
            )
    
    def _build_stop_sale_payload(
        self,
        stop_sale: dict,
        hotel_id: int,
        rec_id: int,
        room_type_ids: list,
        operator_id: int,
        operator_code: str,
        authority_id: int = 207,
    ) -> dict:
        """
        Build Sedna UpdateStopSale request payload.
        
        CRITICAL NOTES:
        - OperatorRemark MUST end with comma for UI visibility!
        - For Phase 1, pass empty arrays
        - For Phase 2, each child must have StopSaleId = rec_id
        
        Args:
            stop_sale: Stop sale record from database
            hotel_id: Sedna hotel ID
            rec_id: 0 for Phase 1 (new), actual ID for Phase 2
            room_type_ids: List of Sedna room type IDs (empty = all rooms)
            operator_id: Sedna operator ID
            operator_code: Operator code (e.g., "7STAR")
            authority_id: Authority ID (default: 207)
            
        Returns:
            Request payload dict
        """
        # Build child arrays
        # Phase 1: Empty arrays (rec_id = 0)
        # Phase 2: Filled arrays with StopSaleId (rec_id > 0)
        stop_sale_rooms = []
        stop_sale_operators = []
        stop_sale_boards = []
        
        if rec_id > 0:  # Phase 2: Fill with data
            # Add room types (if we have IDs)
            for rt_id in room_type_ids:
                stop_sale_rooms.append({
                    "RoomTypeId": rt_id,
                    "State": 1,
                    "StopSaleId": rec_id,
                })
            
            # Always add operator
            stop_sale_operators.append({
                "OperatorId": operator_id,
                "State": 1,
                "StopSaleId": rec_id,
            })
        
        # Format dates
        date_from = stop_sale.get("date_from")
        date_to = stop_sale.get("date_to")
        
        if hasattr(date_from, 'strftime'):
            begin_date = date_from.strftime("%Y-%m-%dT00:00:00")
        else:
            begin_date = str(date_from) + "T00:00:00"
            
        if hasattr(date_to, 'strftime'):
            end_date = date_to.strftime("%Y-%m-%dT00:00:00")
        else:
            end_date = str(date_to) + "T00:00:00"
        
        # Get room type string for visual display
        room_remark = stop_sale.get("room_type") or ""
        
        return {
            "RecId": rec_id,
            "HotelId": hotel_id,
            "BeginDate": begin_date,
            "EndDate": end_date,
            "DeclareDate": datetime.now().strftime("%Y-%m-%dT00:00:00"),
            "Active": 0,
            "RecordUser": "Entegrasyon",
            "RecordSource": 0,
            "StopType": 0 if stop_sale.get("is_close", True) else 1,
            "Authority": authority_id,
            "RoomRemark": room_remark,
            "OperatorRemark": f"{operator_code},",  # ⚠️ MUST end with comma!
            "BoardRemark": "",
            "State": 1,
            "StopSaleRooms": stop_sale_rooms,
            "StopSaleOperators": stop_sale_operators,
            "StopSaleBoards": stop_sale_boards,
            "StopSaleMarkets": [],
        }
    
    async def _find_hotel_id(
        self,
        client: httpx.AsyncClient,
        sedna_config: dict,
        hotel_name: str,
    ) -> Optional[int]:
        """Find hotel ID by name in Sedna."""
        try:
            response = await client.get(
                f"{sedna_config['api_url']}/api/Shop/GetHotels",
                params={
                    "username": sedna_config["username"],
                    "password": sedna_config["password"],
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Find by name (case-insensitive, partial match)
                    hotel_name_lower = hotel_name.lower()
                    for hotel in data:
                        if hotel_name_lower in hotel.get("Name", "").lower():
                            return hotel.get("RecId")
            
            return None
            
        except Exception:
            return None
    
    async def sync_pending(
        self,
        tenant_id: int,
    ) -> dict:
        """
        Sync all pending reservations and stop sales for a tenant.
        
        Returns:
            Summary of sync results
        """
        results = {
            "reservations_synced": 0,
            "reservations_failed": 0,
            "stop_sales_synced": 0,
            "stop_sales_failed": 0,
            "errors": [],
        }
        
        async with self.pool.acquire() as conn:
            # Get pending reservations
            pending_reservations = await conn.fetch(
                """
                SELECT id, source_email_id 
                FROM reservations 
                WHERE tenant_id = $1 AND sedna_synced = false
                LIMIT 50
                """,
                tenant_id,
            )
            
            for res in pending_reservations:
                result = await self.sync_reservation(tenant_id, res["source_email_id"])
                if result.success:
                    results["reservations_synced"] += 1
                else:
                    results["reservations_failed"] += 1
                    results["errors"].append(f"Reservation {res['id']}: {result.message}")
            
            # Get pending stop sales
            pending_stop_sales = await conn.fetch(
                """
                SELECT id 
                FROM stop_sales 
                WHERE tenant_id = $1 AND sedna_synced = false
                LIMIT 50
                """,
                tenant_id,
            )
            
            for ss in pending_stop_sales:
                result = await self.sync_stop_sale(tenant_id, ss["id"])
                if result.success:
                    results["stop_sales_synced"] += 1
                else:
                    results["stop_sales_failed"] += 1
                    results["errors"].append(f"Stop Sale {ss['id']}: {result.message}")
        
        return results
