"""Sedna reference data cache service.

Caches Room Types and Board Types from Sedna API to reduce API calls
and enable code-to-ID lookups.
"""

from datetime import datetime, timedelta
from typing import Optional
import httpx
import asyncpg


class SednaCacheService:
    """
    Cache service for Sedna reference data.
    
    Reduces API calls by caching Room/Board types locally.
    Cache TTL: 24 hours (refreshes automatically when stale).
    
    Usage:
        cache = SednaCacheService(pool)
        room_id = await cache.get_room_type_id(tenant_id, "STDSV", sedna_config)
        board_id = await cache.get_board_id("AI", sedna_config)
    """
    
    CACHE_TTL = timedelta(hours=24)
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        # Per-tenant room type cache: {tenant_id: {code: id}}
        self._room_types: dict[int, dict[str, int]] = {}
        self._room_types_refresh: dict[int, datetime] = {}
        
        # Global board type cache (same across tenants)
        self._board_types: dict[str, int] = {}
        self._board_types_refresh: Optional[datetime] = None
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    async def get_room_type_id(
        self,
        tenant_id: int,
        code: str,
        sedna_config: dict,
    ) -> Optional[int]:
        """
        Get Sedna RoomTypeId from room code.
        
        Args:
            tenant_id: Tenant ID
            code: Room type code (e.g., "STDSV", "STDLV")
            sedna_config: Sedna API config with api_url, operator_id
            
        Returns:
            RoomTypeId or None if not found
        """
        if self._should_refresh_room_types(tenant_id):
            await self.refresh_room_types(tenant_id, sedna_config)
        
        tenant_rooms = self._room_types.get(tenant_id, {})
        return tenant_rooms.get(code.upper().strip())
    
    async def get_room_type_ids(
        self,
        tenant_id: int,
        codes: list[str],
        sedna_config: dict,
    ) -> list[int]:
        """
        Get multiple Sedna RoomTypeIds from room codes.
        
        Args:
            tenant_id: Tenant ID
            codes: List of room type codes
            sedna_config: Sedna API config
            
        Returns:
            List of RoomTypeIds (only found ones)
        """
        result = []
        for code in codes:
            room_id = await self.get_room_type_id(tenant_id, code, sedna_config)
            if room_id:
                result.append(room_id)
        return result
    
    async def get_board_id(
        self,
        code: str,
        sedna_config: dict,
    ) -> Optional[int]:
        """
        Get Sedna BoardId from board code.
        
        Args:
            code: Board type code (e.g., "AI", "UAI", "HB", "FB")
            sedna_config: Sedna API config
            
        Returns:
            BoardId or None if not found
        """
        if self._should_refresh_board_types():
            await self.refresh_board_types(sedna_config)
        
        return self._board_types.get(code.upper().strip())
    
    async def get_board_ids(
        self,
        codes: list[str],
        sedna_config: dict,
    ) -> list[int]:
        """
        Get multiple Sedna BoardIds from board codes.
        
        Args:
            codes: List of board type codes
            sedna_config: Sedna API config
            
        Returns:
            List of BoardIds (only found ones)
        """
        result = []
        for code in codes:
            board_id = await self.get_board_id(code, sedna_config)
            if board_id:
                result.append(board_id)
        return result
    
    # =========================================================================
    # Cache Refresh
    # =========================================================================
    
    async def refresh_room_types(
        self,
        tenant_id: int,
        sedna_config: dict,
    ) -> bool:
        """
        Fetch room types from Sedna API and update cache.
        
        Endpoint: POST /api/Integratiion/GetRoomTypeList?operatorId={id}
        
        Args:
            tenant_id: Tenant ID
            sedna_config: Sedna API config
            
        Returns:
            True if refresh successful
        """
        try:
            operator_id = sedna_config.get("operator_id", 571)
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{sedna_config['api_url']}/api/Integratiion/GetRoomTypeList",
                    params={"operatorId": operator_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse response - might be wrapped in Data or direct array
                    items = data.get("Data", data) if isinstance(data, dict) else data
                    
                    if isinstance(items, list):
                        self._room_types[tenant_id] = {}
                        for item in items:
                            code = item.get("Code") or item.get("code")
                            room_id = item.get("RoomTypeId") or item.get("roomTypeId") or item.get("Id") or item.get("id")
                            if code and room_id:
                                self._room_types[tenant_id][code.upper().strip()] = int(room_id)
                        
                        self._room_types_refresh[tenant_id] = datetime.now()
                        return True
            
            return False
            
        except Exception as e:
            print(f"Error refreshing room types: {e}")
            return False
    
    async def refresh_board_types(
        self,
        sedna_config: dict,
    ) -> bool:
        """
        Fetch board types from Sedna API and update cache.
        
        Endpoint: GET /api/Service2/GetBoardList
        
        Args:
            sedna_config: Sedna API config
            
        Returns:
            True if refresh successful
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{sedna_config['api_url']}/api/Service2/GetBoardList"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse response
                    items = data.get("Data", data) if isinstance(data, dict) else data
                    
                    if isinstance(items, list):
                        self._board_types = {}
                        for item in items:
                            code = item.get("Code") or item.get("code")
                            board_id = item.get("BoardId") or item.get("boardId") or item.get("Id") or item.get("id")
                            if code and board_id:
                                self._board_types[code.upper().strip()] = int(board_id)
                        
                        self._board_types_refresh = datetime.now()
                        return True
            
            return False
            
        except Exception as e:
            print(f"Error refreshing board types: {e}")
            return False
    
    # =========================================================================
    # Cache Status
    # =========================================================================
    
    def get_cache_stats(self, tenant_id: int = None) -> dict:
        """Get cache statistics for monitoring."""
        stats = {
            "board_types_count": len(self._board_types),
            "board_types_last_refresh": self._board_types_refresh.isoformat() if self._board_types_refresh else None,
        }
        
        if tenant_id:
            stats["room_types_count"] = len(self._room_types.get(tenant_id, {}))
            refresh_time = self._room_types_refresh.get(tenant_id)
            stats["room_types_last_refresh"] = refresh_time.isoformat() if refresh_time else None
        else:
            stats["room_types_tenants"] = list(self._room_types.keys())
        
        return stats
    
    def clear_cache(self, tenant_id: int = None) -> None:
        """Clear cache (useful for testing or forced refresh)."""
        if tenant_id:
            self._room_types.pop(tenant_id, None)
            self._room_types_refresh.pop(tenant_id, None)
        else:
            self._room_types.clear()
            self._room_types_refresh.clear()
            self._board_types.clear()
            self._board_types_refresh = None
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _should_refresh_room_types(self, tenant_id: int) -> bool:
        """Check if room types cache needs refresh."""
        if tenant_id not in self._room_types:
            return True
        
        last_refresh = self._room_types_refresh.get(tenant_id)
        if not last_refresh:
            return True
        
        return datetime.now() - last_refresh > self.CACHE_TTL
    
    def _should_refresh_board_types(self) -> bool:
        """Check if board types cache needs refresh."""
        if not self._board_types:
            return True
        
        if not self._board_types_refresh:
            return True
        
        return datetime.now() - self._board_types_refresh > self.CACHE_TTL


# =============================================================================
# Singleton instance (set from main.py)
# =============================================================================

_cache_service: Optional[SednaCacheService] = None


def get_cache_service() -> SednaCacheService:
    """Get the global cache service instance."""
    if _cache_service is None:
        raise RuntimeError("SednaCacheService not initialized")
    return _cache_service


def set_cache_service(service: SednaCacheService) -> None:
    """Set the global cache service instance."""
    global _cache_service
    _cache_service = service
