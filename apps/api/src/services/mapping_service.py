"""Mapping service for Juniper to Sedna data conversion."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.services.sedna_client import SednaClient, SednaHotel, SednaRoomType, SednaCountry
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MappingEntry(BaseModel):
    """A single mapping entry."""

    source_value: str  # Juniper value
    target_id: int  # Sedna ID
    target_name: str | None = None  # Sedna name for reference


class MappingCache(BaseModel):
    """Complete mapping cache."""

    hotels: dict[str, MappingEntry] = {}  # Hotel name -> Sedna HotelId
    room_types: dict[str, dict[str, MappingEntry]] = {}  # Hotel name -> {Room code -> Sedna RoomTypeId}
    boards: dict[str, MappingEntry] = {}  # Board code -> Sedna BoardId
    countries: dict[str, MappingEntry] = {}  # Country name -> Sedna NationalityId
    transfer_types: dict[str, MappingEntry] = {}  # Transfer type name -> Sedna TransferTypeId

    # Reverse mappings (ID -> name)
    hotel_ids: dict[int, str] = {}
    room_type_ids: dict[int, str] = {}


class MappingService:
    """
    Service for mapping Juniper data to Sedna IDs.

    This service maintains a cache of mappings between Juniper hotel/room/board names
    and Sedna IDs. It can be populated from the Sedna API or loaded from a JSON file.
    """

    # Default board mapping (can be overridden)
    DEFAULT_BOARD_MAPPING = {
        "AI": MappingEntry(source_value="AI", target_id=1, target_name="All Inclusive"),
        "ALL INCLUSIVE": MappingEntry(source_value="ALL INCLUSIVE", target_id=1, target_name="All Inclusive"),
        "FB": MappingEntry(source_value="FB", target_id=2, target_name="Full Board"),
        "FULL BOARD": MappingEntry(source_value="FULL BOARD", target_id=2, target_name="Full Board"),
        "HB": MappingEntry(source_value="HB", target_id=4, target_name="Half Board"),
        "HALF BOARD": MappingEntry(source_value="HALF BOARD", target_id=4, target_name="Half Board"),
        "BB": MappingEntry(source_value="BB", target_id=3, target_name="Bed & Breakfast"),
        "BED AND BREAKFAST": MappingEntry(source_value="BED AND BREAKFAST", target_id=3, target_name="Bed & Breakfast"),
        "RO": MappingEntry(source_value="RO", target_id=5, target_name="Room Only"),
        "ROOM ONLY": MappingEntry(source_value="ROOM ONLY", target_id=5, target_name="Room Only"),
        "UAI": MappingEntry(source_value="UAI", target_id=6, target_name="Ultra All Inclusive"),
        "ULTRA ALL INCLUSIVE": MappingEntry(source_value="ULTRA ALL INCLUSIVE", target_id=6, target_name="Ultra All Inclusive"),
    }

    def __init__(self, cache_file: str | Path | None = None):
        """
        Initialize mapping service.

        Args:
            cache_file: Optional path to JSON cache file
        """
        self.cache = MappingCache()
        self.cache_file = Path(cache_file) if cache_file else None

        # Initialize default board mapping
        self.cache.boards = self.DEFAULT_BOARD_MAPPING.copy()

        # Load from file if exists
        if self.cache_file and self.cache_file.exists():
            self.load_from_file()

    def load_from_file(self) -> None:
        """Load mapping cache from JSON file."""
        if not self.cache_file or not self.cache_file.exists():
            logger.warning("mapping_file_not_found", path=str(self.cache_file))
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse into cache
            self.cache = MappingCache.model_validate(data)
            logger.info(
                "mapping_loaded_from_file",
                path=str(self.cache_file),
                hotels=len(self.cache.hotels),
                countries=len(self.cache.countries),
            )
        except Exception as e:
            logger.error("mapping_load_error", error=str(e))

    def save_to_file(self) -> None:
        """Save mapping cache to JSON file."""
        if not self.cache_file:
            logger.warning("no_cache_file_configured")
            return

        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache.model_dump(), f, indent=2, ensure_ascii=False)

            logger.info("mapping_saved_to_file", path=str(self.cache_file))
        except Exception as e:
            logger.error("mapping_save_error", error=str(e))

    async def populate_from_sedna(self, client: SednaClient) -> None:
        """
        Populate mapping cache from Sedna API.

        Args:
            client: Initialized SednaClient
        """
        logger.info("populating_mapping_from_sedna")

        # Get hotels
        hotels = await client.get_hotels()
        for hotel in hotels:
            key = self._normalize_key(hotel.Name)
            self.cache.hotels[key] = MappingEntry(
                source_value=hotel.Name,
                target_id=hotel.RecId,
                target_name=hotel.Name,
            )
            self.cache.hotel_ids[hotel.RecId] = hotel.Name

        logger.info("hotels_mapped", count=len(self.cache.hotels))

        # Get room types for all hotels
        hotel_ids = [h.RecId for h in hotels]
        if hotel_ids:
            room_types_by_hotel = await client.get_room_types(hotel_ids)
            for hotel_id, room_types in room_types_by_hotel.items():
                hotel_name = self.cache.hotel_ids.get(hotel_id, str(hotel_id))
                hotel_key = self._normalize_key(hotel_name)

                if hotel_key not in self.cache.room_types:
                    self.cache.room_types[hotel_key] = {}

                for rt in room_types:
                    rt_key = self._normalize_key(rt.Code or rt.Name)
                    self.cache.room_types[hotel_key][rt_key] = MappingEntry(
                        source_value=rt.Code or rt.Name,
                        target_id=rt.RecId,
                        target_name=rt.Name,
                    )
                    self.cache.room_type_ids[rt.RecId] = rt.Name

        logger.info("room_types_mapped", hotels=len(self.cache.room_types))

        # Get countries
        countries = await client.get_countries()
        for country in countries:
            key = self._normalize_key(country.Name)
            self.cache.countries[key] = MappingEntry(
                source_value=country.Name,
                target_id=country.RecId,
                target_name=country.Name,
            )

        logger.info("countries_mapped", count=len(self.cache.countries))

        # Get transfer types
        transfer_types = await client.get_transfer_types()
        for tt in transfer_types:
            key = self._normalize_key(tt.Name)
            self.cache.transfer_types[key] = MappingEntry(
                source_value=tt.Name,
                target_id=tt.RecId,
                target_name=tt.Name,
            )

        logger.info("transfer_types_mapped", count=len(self.cache.transfer_types))

        # Save to file if configured
        if self.cache_file:
            self.save_to_file()

    @staticmethod
    def _normalize_key(value: str) -> str:
        """Normalize a string for use as a mapping key."""
        return value.upper().strip()

    def get_hotel_id(self, hotel_name: str) -> int | None:
        """
        Get Sedna HotelId for a hotel name.

        Args:
            hotel_name: Hotel name from Juniper

        Returns:
            Sedna HotelId or None if not found
        """
        key = self._normalize_key(hotel_name)
        entry = self.cache.hotels.get(key)
        return entry.target_id if entry else None

    def get_room_type_id(self, hotel_name: str, room_code: str) -> int | None:
        """
        Get Sedna RoomTypeId for a room type.

        Args:
            hotel_name: Hotel name
            room_code: Room type code from Juniper

        Returns:
            Sedna RoomTypeId or None if not found
        """
        hotel_key = self._normalize_key(hotel_name)
        room_key = self._normalize_key(room_code)

        room_types = self.cache.room_types.get(hotel_key, {})
        entry = room_types.get(room_key)
        return entry.target_id if entry else None

    def get_board_id(self, board_code: str) -> int | None:
        """
        Get Sedna BoardId for a board code.

        Args:
            board_code: Board code from Juniper (AI, FB, HB, etc.)

        Returns:
            Sedna BoardId or None if not found
        """
        key = self._normalize_key(board_code)
        entry = self.cache.boards.get(key)
        return entry.target_id if entry else None

    def get_country_id(self, country_name: str) -> int | None:
        """
        Get Sedna NationalityId for a country name.

        Args:
            country_name: Country name from Juniper

        Returns:
            Sedna NationalityId or None if not found
        """
        key = self._normalize_key(country_name)
        entry = self.cache.countries.get(key)
        return entry.target_id if entry else None

    def get_transfer_type_id(self, transfer_type: str) -> int | None:
        """
        Get Sedna TransferTypeId for a transfer type name.

        Args:
            transfer_type: Transfer type name

        Returns:
            Sedna TransferTypeId or None if not found
        """
        key = self._normalize_key(transfer_type)
        entry = self.cache.transfer_types.get(key)
        return entry.target_id if entry else None

    def add_hotel_mapping(self, juniper_name: str, sedna_id: int, sedna_name: str | None = None) -> None:
        """Manually add a hotel mapping."""
        key = self._normalize_key(juniper_name)
        self.cache.hotels[key] = MappingEntry(
            source_value=juniper_name,
            target_id=sedna_id,
            target_name=sedna_name or juniper_name,
        )
        self.cache.hotel_ids[sedna_id] = sedna_name or juniper_name

    def add_room_type_mapping(
        self,
        hotel_name: str,
        juniper_code: str,
        sedna_id: int,
        sedna_name: str | None = None,
    ) -> None:
        """Manually add a room type mapping."""
        hotel_key = self._normalize_key(hotel_name)
        room_key = self._normalize_key(juniper_code)

        if hotel_key not in self.cache.room_types:
            self.cache.room_types[hotel_key] = {}

        self.cache.room_types[hotel_key][room_key] = MappingEntry(
            source_value=juniper_code,
            target_id=sedna_id,
            target_name=sedna_name or juniper_code,
        )

    def add_board_mapping(self, juniper_code: str, sedna_id: int, sedna_name: str | None = None) -> None:
        """Manually add a board type mapping."""
        key = self._normalize_key(juniper_code)
        self.cache.boards[key] = MappingEntry(
            source_value=juniper_code,
            target_id=sedna_id,
            target_name=sedna_name or juniper_code,
        )

    def get_mapping_stats(self) -> dict[str, int]:
        """Get statistics about the mapping cache."""
        return {
            "hotels": len(self.cache.hotels),
            "room_types_hotels": len(self.cache.room_types),
            "room_types_total": sum(len(rts) for rts in self.cache.room_types.values()),
            "boards": len(self.cache.boards),
            "countries": len(self.cache.countries),
            "transfer_types": len(self.cache.transfer_types),
        }
