"""Sedna API routes for hotel search and management."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from auth.routes import get_current_user, UserResponse
from tenant.routes import get_settings_service
from sedna.hotel_service import (
    get_hotel_search_service,
    get_hotel_mapping_service,
)


router = APIRouter(prefix="/api/sedna", tags=["Sedna"])


# =============================================================================
# Request/Response Models
# =============================================================================


class HotelSuggestion(BaseModel):
    """A hotel suggestion with similarity score."""
    id: int
    name: str
    similarity: float


class HotelSearchResponse(BaseModel):
    """Response from hotel search."""
    query: str
    query_normalized: str
    exact_match: Optional[dict] = None
    suggestions: list[HotelSuggestion] = []
    cached: bool = False
    from_mapping: bool = False
    error: Optional[str] = None


class AssignHotelRequest(BaseModel):
    """Request to assign hotel to stop sale."""
    sedna_hotel_id: int
    save_mapping: bool = True


class AssignHotelResponse(BaseModel):
    """Response from hotel assignment."""
    success: bool
    stop_sale_id: int
    sedna_hotel_id: int
    hotel_name: Optional[str] = None
    mapping_saved: bool = False


class HotelMappingItem(BaseModel):
    """A hotel mapping record."""
    hotel_name: str
    sedna_hotel_id: int
    sedna_hotel_name: Optional[str] = None
    created_at: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/hotels/search", response_model=HotelSearchResponse)
async def search_hotels(
    q: str = Query(..., description="Hotel name to search"),
    limit: int = Query(10, le=20, description="Max results"),
    min_score: int = Query(50, ge=0, le=100, description="Minimum similarity %"),
    user: UserResponse = Depends(get_current_user),
):
    """
    Search hotels by name with fuzzy matching.
    
    Returns exact match if found, otherwise returns similar hotels
    sorted by similarity score.
    
    Uses rapidfuzz for fast fuzzy string matching.
    Cache TTL: 24 hours.
    """
    if not q or len(q) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")
    
    # Get Sedna config
    settings_service = get_settings_service()
    credentials = await settings_service.get_decrypted_credentials(user.tenant_id)
    
    if not credentials or not credentials.get("sedna"):
        raise HTTPException(400, "Sedna not configured")
    
    sedna_config = credentials["sedna"]
    
    # Search
    search_service = get_hotel_search_service()
    result = await search_service.search_hotels(
        query=q,
        tenant_id=user.tenant_id,
        sedna_config=sedna_config,
        limit=limit,
        min_score=min_score,
    )
    
    return HotelSearchResponse(**result)


@router.post("/stop-sales/{stop_sale_id}/assign-hotel", response_model=AssignHotelResponse)
async def assign_hotel_to_stop_sale(
    stop_sale_id: int,
    request: AssignHotelRequest,
    user: UserResponse = Depends(get_current_user),
):
    """
    Assign a Sedna hotel ID to a stop sale record.
    
    Optionally saves the mapping for future automatic matching.
    """
    from sedna.hotel_service import get_hotel_mapping_service
    import asyncpg
    from main import pool
    
    # Get stop sale
    async with pool.acquire() as conn:
        stop_sale = await conn.fetchrow(
            "SELECT * FROM stop_sales WHERE id = $1 AND tenant_id = $2",
            stop_sale_id, user.tenant_id,
        )
        
        if not stop_sale:
            raise HTTPException(404, "Stop sale not found")
        
        # Update sedna_hotel_id
        await conn.execute(
            "UPDATE stop_sales SET sedna_hotel_id = $1 WHERE id = $2",
            request.sedna_hotel_id, stop_sale_id,
        )
    
    # Get hotel name from Sedna
    hotel_name = None
    try:
        settings_service = get_settings_service()
        credentials = await settings_service.get_decrypted_credentials(user.tenant_id)
        sedna_config = credentials.get("sedna", {}) if credentials else {}
        
        search_service = get_hotel_search_service()
        hotel = await search_service.get_hotel_by_id(
            request.sedna_hotel_id,
            user.tenant_id,
            sedna_config,
        )
        hotel_name = hotel.get("name") if hotel else None
    except Exception:
        pass
    
    # Save mapping if requested
    mapping_saved = False
    if request.save_mapping and stop_sale.get("hotel_name"):
        try:
            mapping_service = get_hotel_mapping_service()
            await mapping_service.create_mapping(
                tenant_id=user.tenant_id,
                hotel_name_original=stop_sale["hotel_name"],
                sedna_hotel_id=request.sedna_hotel_id,
                sedna_hotel_name=hotel_name,
                user_id=user.id if hasattr(user, 'id') else None,
            )
            mapping_saved = True
        except Exception as e:
            print(f"Failed to save mapping: {e}")
    
    return AssignHotelResponse(
        success=True,
        stop_sale_id=stop_sale_id,
        sedna_hotel_id=request.sedna_hotel_id,
        hotel_name=hotel_name,
        mapping_saved=mapping_saved,
    )


@router.get("/hotels/mappings", response_model=list[HotelMappingItem])
async def list_hotel_mappings(
    limit: int = Query(50, le=100),
    user: UserResponse = Depends(get_current_user),
):
    """
    List all hotel mappings for the tenant.
    
    Shows which email hotel names map to which Sedna hotel IDs.
    """
    mapping_service = get_hotel_mapping_service()
    mappings = await mapping_service.list_mappings(user.tenant_id, limit)
    
    return [HotelMappingItem(**m) for m in mappings]


@router.delete("/hotels/mappings/{hotel_name}")
async def delete_hotel_mapping(
    hotel_name: str,
    user: UserResponse = Depends(get_current_user),
):
    """Delete a hotel mapping."""
    mapping_service = get_hotel_mapping_service()
    success = await mapping_service.delete_mapping(user.tenant_id, hotel_name)
    
    if not success:
        raise HTTPException(404, "Mapping not found")
    
    return {"success": True, "message": "Mapping deleted"}
