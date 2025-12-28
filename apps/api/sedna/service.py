"""Tenant-aware Sedna sync service."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
import asyncpg

from tenant.service import TenantSettingsService


@dataclass
class SyncResult:
    """Result of sync operation."""
    
    success: bool
    message: str
    sedna_rec_id: Optional[int] = None
    details: dict = field(default_factory=dict)


class TenantSednaService:
    """Tenant-aware Sedna sync service."""
    
    def __init__(self, pool: asyncpg.Pool, settings_service: TenantSettingsService):
        self.pool = pool
        self.settings_service = settings_service
    
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
        Sync a stop sale to Sedna.
        
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
            
            if stop_sale["sedna_synced"]:
                return SyncResult(
                    success=True,
                    message="Already synced",
                )
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Find hotel ID
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
                
                # Create stop sale in Sedna
                response = await client.post(
                    f"{sedna_config['api_url']}/api/StopSale/InsertStopSale",
                    json={
                        "HotelId": hotel_id,
                        "BeginDate": stop_sale["date_from"].strftime("%Y-%m-%d"),
                        "EndDate": stop_sale["date_to"].strftime("%Y-%m-%d"),
                        "IsClose": stop_sale["is_close"],
                    },
                    params={
                        "username": sedna_config["username"],
                        "password": sedna_config["password"],
                    },
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ErrorType") == 0:
                        # Update stop sale
                        async with self.pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE stop_sales 
                                SET sedna_synced = true, sedna_rec_id = $1
                                WHERE id = $2 AND tenant_id = $3
                                """,
                                data.get("RecId"),
                                stop_sale_id,
                                tenant_id,
                            )
                        
                        return SyncResult(
                            success=True,
                            message="Synced successfully",
                            sedna_rec_id=data.get("RecId"),
                        )
                    else:
                        return SyncResult(
                            success=False,
                            message=data.get("Message", "Sedna API error"),
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
