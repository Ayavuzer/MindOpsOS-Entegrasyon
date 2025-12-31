"""Sedna Agency API client for integration with MindOps."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.utils.logger import get_logger, mask_sensitive

logger = get_logger(__name__)


# =============================================================================
# API Response Models
# =============================================================================


class SednaApiResponse(BaseModel):
    """Standard Sedna API response wrapper."""

    ErrorType: int = 0  # 0 = Success
    Message: str | None = None
    RecId: int | None = None


class SednaHotel(BaseModel):
    """Hotel data from Sedna."""

    RecId: int
    Name: str
    Code: str | None = None
    RegionId: int | None = None
    RegionName: str | None = None
    IsActive: bool = True


class SednaRoomType(BaseModel):
    """Room type data from Sedna."""

    RecId: int
    Code: str | None = None
    Name: str
    HotelId: int


class SednaCountry(BaseModel):
    """Country/Nationality data from Sedna."""

    RecId: int
    Name: str
    Code: str | None = None


class SednaOperator(BaseModel):
    """Operator data from Sedna."""

    RecId: int
    Name: str
    Code: str | None = None


class SednaTransferType(BaseModel):
    """Transfer type data from Sedna."""

    RecId: int
    Name: str
    Code: str | None = None


class SednaStopSale(BaseModel):
    """Stop sale data from Sedna."""

    RecId: int | None = None
    HotelId: int
    HotelName: str | None = None
    BeginDate: str
    EndDate: str
    RoomTypeId: int | None = None
    RoomTypeName: str | None = None
    BoardId: int | None = None
    BoardName: str | None = None
    IsClose: bool = True
    RecordDate: str | None = None
    UpdateDate: str | None = None


# =============================================================================
# Request Models
# =============================================================================


class CustomerRequest(BaseModel):
    """Customer data for reservation request."""

    Title: str = "Mr"  # Mr, Mrs, Grp, Chd, Inf
    FirstName: str
    LastName: str
    BirthDate: str | None = None  # YYYY-MM-DD
    Age: int | None = None
    PassNo: str | None = None
    PassSerial: str | None = None
    Nationality: str | None = None
    NationalityId: int | None = None
    SourceId: str | None = None

    # Transfer info
    ArrivalFlightNumber: str | None = None
    DepartureFlightNumber: str | None = None
    ArrivalFlightTime: str | None = None  # YYYY-MM-DD
    DepartureFlightTime: str | None = None  # YYYY-MM-DD
    ArrTransferType: int | None = None
    DepTransferType: int | None = None
    IsArrivalTransfer: int = 0  # 0 or 1
    IsDepartureTransfer: int = 0  # 0 or 1


class ReservationRequest(BaseModel):
    """Reservation request for InsertReservation API."""

    # Required fields
    HotelId: int
    OperatorId: int
    CheckinDate: str  # YYYY-MM-DD
    CheckOutDate: str  # YYYY-MM-DD
    Adult: int
    Child: int = 0
    BoardId: int
    RoomTypeId: int
    Customers: list[CustomerRequest]

    # Optional fields
    Voucher: str | None = None
    SourceId: str | None = None
    ContractId: int | None = None
    Amount: Decimal | None = None
    SaleDate: str | None = None  # YYYY-MM-DD
    
    # Remarks
    HotelRemark: str | None = None
    ReservationRemark: str | None = None
    Remark: str | None = None
    Code1: str | None = None
    Code2: str | None = None
    Code3: str | None = None

    # Flags
    IsReservationChanged: bool = False
    IsBabyFree: bool = True
    CheckContract: bool = True


class ReservationFilter(BaseModel):
    """Filter for GetReservations API."""

    VoucherNo: str | None = None
    SourceId: str | None = None
    RecId: int | None = None
    OperatorId: int | None = None
    HotelId: int | None = None
    RecordDateBegin: str | None = None
    RecordDateEnd: str | None = None
    UpdateDateBegin: str | None = None
    UpdateDateEnd: str | None = None


class StopSaleFilter(BaseModel):
    """Filter for GetStopSaleList API."""

    hotelId: int
    recordDateBegin: str | None = None
    recordDateEnd: str | None = None
    stopDateBegin: str | None = None
    stopDateEnd: str | None = None


# =============================================================================
# Exceptions
# =============================================================================


class SednaApiError(Exception):
    """Base exception for Sedna API errors."""

    def __init__(self, message: str, error_type: int = -1, response: Any = None):
        super().__init__(message)
        self.error_type = error_type
        self.response = response


class SednaAuthError(SednaApiError):
    """Authentication error."""

    pass


class SednaValidationError(SednaApiError):
    """Validation error from API."""

    pass


# =============================================================================
# Sedna Client
# =============================================================================


class SednaClient:
    """
    Async client for Sedna Agency API.

    Usage:
        async with SednaClient(base_url, username, password) as client:
            hotels = await client.get_hotels()
            result = await client.insert_reservation(reservation)
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 30,
    ):
        """
        Initialize Sedna client.

        Args:
            base_url: API base URL (e.g., http://test.kodsedna.com/SednaAgencyb2bApi/api)
            username: API username
            password: API password
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.operator_id: int | None = None
        self._client: httpx.AsyncClient | None = None

        # Cache for master data
        self._hotels_cache: dict[int, SednaHotel] = {}
        self._room_types_cache: dict[int, dict[int, SednaRoomType]] = {}
        self._countries_cache: dict[int, SednaCountry] = {}

    async def __aenter__(self) -> "SednaClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        # Auto-login on context entry
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, raise if not initialized."""
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with SednaClient(...)' context.")
        return self._client

    # =========================================================================
    # Authentication
    # =========================================================================

    async def login(self) -> int:
        """
        Login to Sedna API and get OperatorId.

        Returns:
            OperatorId (RecId from response)

        Raises:
            SednaAuthError: If login fails
        """
        logger.info(
            "sedna_login_attempt",
            username=self.username,
            password=mask_sensitive(self.password),
        )

        # Note: API path has typo "Integratiion"
        url = f"{self.base_url}/Integratiion/AgencyLogin"
        params = {
            "username": self.username,
            "password": self.password,
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("ErrorType", -1) != 0:
                raise SednaAuthError(
                    f"Login failed: {data.get('Message', 'Unknown error')}",
                    error_type=data.get("ErrorType", -1),
                    response=data,
                )

            self.operator_id = data.get("RecId")
            logger.info("sedna_login_success", operator_id=self.operator_id)
            return self.operator_id

        except httpx.HTTPStatusError as e:
            logger.error("sedna_login_http_error", status=e.response.status_code)
            raise SednaAuthError(f"HTTP error during login: {e}") from e
        except Exception as e:
            logger.error("sedna_login_error", error=str(e))
            raise SednaAuthError(f"Login error: {e}") from e

    # =========================================================================
    # Hotel & Master Data
    # =========================================================================

    async def get_hotels(self, is_active: bool = True, use_cache: bool = True) -> list[SednaHotel]:
        """
        Get list of hotels.

        Args:
            is_active: Filter active hotels only
            use_cache: Use cached data if available

        Returns:
            List of SednaHotel objects
        """
        if use_cache and self._hotels_cache:
            return list(self._hotels_cache.values())

        if not self.operator_id:
            await self.login()

        url = f"{self.base_url}/Integratiion/GetHotelList"
        params = {
            "operatorId": self.operator_id,
            "isActive": str(is_active).lower(),
        }

        logger.debug("sedna_get_hotels", operator_id=self.operator_id)

        response = await self.client.post(url, params=params)
        response.raise_for_status()
        data = response.json()

        hotels = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            hotel = SednaHotel(
                RecId=item.get("RecId", item.get("HotelId", 0)),
                Name=item.get("Name", item.get("HotelName", "")),
                Code=item.get("Code"),
                RegionId=item.get("RegionId"),
                RegionName=item.get("RegionName"),
                IsActive=item.get("IsActive", True),
            )
            hotels.append(hotel)
            self._hotels_cache[hotel.RecId] = hotel

        logger.info("sedna_hotels_loaded", count=len(hotels))
        return hotels

    async def get_room_types(self, hotel_ids: list[int]) -> dict[int, list[SednaRoomType]]:
        """
        Get room types for specified hotels.

        Args:
            hotel_ids: List of hotel IDs

        Returns:
            Dict mapping hotel_id -> list of room types
        """
        url = f"{self.base_url}/Service1/GetHotelRoomTypelistAll"

        logger.debug("sedna_get_room_types", hotel_ids=hotel_ids)

        response = await self.client.post(url, json=hotel_ids)
        response.raise_for_status()
        data = response.json()

        result: dict[int, list[SednaRoomType]] = {}

        for item in data if isinstance(data, list) else data.get("Data", []):
            hotel_id = item.get("HotelId", 0)
            room_type = SednaRoomType(
                RecId=item.get("RecId", item.get("RoomTypeId", 0)),
                Code=item.get("Code"),
                Name=item.get("Name", item.get("RoomTypeName", "")),
                HotelId=hotel_id,
            )

            if hotel_id not in result:
                result[hotel_id] = []
            result[hotel_id].append(room_type)

            # Update cache
            if hotel_id not in self._room_types_cache:
                self._room_types_cache[hotel_id] = {}
            self._room_types_cache[hotel_id][room_type.RecId] = room_type

        logger.info("sedna_room_types_loaded", hotel_count=len(result))
        return result

    async def get_countries(self) -> list[SednaCountry]:
        """Get list of countries/nationalities."""
        url = f"{self.base_url}/Integratiion/GetCountrys"

        response = await self.client.post(url)
        response.raise_for_status()
        data = response.json()

        countries = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            country = SednaCountry(
                RecId=item.get("RecId", item.get("NationalityId", 0)),
                Name=item.get("Name", ""),
                Code=item.get("Code"),
            )
            countries.append(country)
            self._countries_cache[country.RecId] = country

        logger.info("sedna_countries_loaded", count=len(countries))
        return countries

    async def get_operators(self) -> list[SednaOperator]:
        """Get list of operators."""
        url = f"{self.base_url}/Integratiion/GetOperators"

        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()

        operators = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            operators.append(
                SednaOperator(
                    RecId=item.get("RecId", 0),
                    Name=item.get("Name", ""),
                    Code=item.get("Code"),
                )
            )

        logger.info("sedna_operators_loaded", count=len(operators))
        return operators

    async def get_transfer_types(self) -> list[SednaTransferType]:
        """Get list of transfer types."""
        url = f"{self.base_url}/Integratiion/GetTransferTypeForIntegration"

        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()

        transfer_types = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            transfer_types.append(
                SednaTransferType(
                    RecId=item.get("RecId", 0),
                    Name=item.get("Name", ""),
                    Code=item.get("Code"),
                )
            )

        logger.info("sedna_transfer_types_loaded", count=len(transfer_types))
        return transfer_types

    # =========================================================================
    # Reservations
    # =========================================================================

    async def insert_reservation(
        self,
        reservation: ReservationRequest,
        voucher_no: str,
    ) -> SednaApiResponse:
        """
        Insert a new reservation into Sedna.

        Args:
            reservation: ReservationRequest object
            voucher_no: Voucher number (required, passed as query param)

        Returns:
            SednaApiResponse with RecId of created reservation

        Raises:
            SednaValidationError: If validation fails
            SednaApiError: If API returns error
        """
        url = f"{self.base_url}/Integratiion/InsertReservation"
        params = {
            "username": self.username,
            "password": self.password,
            "voucherNo": voucher_no,
        }

        # API expects array of reservations
        payload = [reservation.model_dump(exclude_none=True)]

        logger.info(
            "sedna_insert_reservation",
            voucher=voucher_no,
            hotel_id=reservation.HotelId,
            check_in=reservation.CheckinDate,
            check_out=reservation.CheckOutDate,
            adults=reservation.Adult,
            children=reservation.Child,
        )

        try:
            response = await self.client.post(url, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

            # Handle response
            if isinstance(data, list) and len(data) > 0:
                result_data = data[0]
            else:
                result_data = data

            result = SednaApiResponse(
                ErrorType=result_data.get("ErrorType", 0),
                Message=result_data.get("Message"),
                RecId=result_data.get("RecId"),
            )

            if result.ErrorType != 0:
                logger.error(
                    "sedna_reservation_error",
                    voucher=voucher_no,
                    error_type=result.ErrorType,
                    message=result.Message,
                )
                raise SednaValidationError(
                    f"Reservation failed: {result.Message}",
                    error_type=result.ErrorType,
                    response=result_data,
                )

            logger.info(
                "sedna_reservation_success",
                voucher=voucher_no,
                rec_id=result.RecId,
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error("sedna_reservation_http_error", status=e.response.status_code)
            raise SednaApiError(f"HTTP error: {e}") from e

    async def get_reservations(self, filter: ReservationFilter) -> list[dict]:
        """
        Get reservations with optional filters.

        Args:
            filter: ReservationFilter object

        Returns:
            List of reservation dictionaries
        """
        url = f"{self.base_url}/Integratiion/GetReservations"
        payload = filter.model_dump(exclude_none=True)

        logger.debug("sedna_get_reservations", filter=payload)

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        reservations = data if isinstance(data, list) else data.get("Data", [])
        logger.info("sedna_reservations_found", count=len(reservations))
        return reservations

    async def get_reservation_by_voucher(
        self,
        voucher: str,
        operator_id: int | None = None,
    ) -> dict | None:
        """
        Get reservation by voucher number.

        Args:
            voucher: Voucher number
            operator_id: Optional operator ID (uses login operator if not provided)

        Returns:
            Reservation dict or None if not found
        """
        url = f"{self.base_url}/Reservation/GetReservationByVoucher"
        params = {
            "voucher": voucher,
            "operatorId": operator_id or self.operator_id,
        }

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data and not data.get("ErrorType"):
            return data
        return None

    async def cancel_reservation_by_source_id(
        self,
        source_id: str,
        operator_id: int | None = None,
    ) -> SednaApiResponse:
        """
        Cancel reservation by SourceId.

        Args:
            source_id: External source ID
            operator_id: Optional operator ID

        Returns:
            SednaApiResponse
        """
        url = f"{self.base_url}/Integratiion/CancelReservationBySourcId"
        params = {
            "operatorId": operator_id or self.operator_id,
            "sourceId": source_id,
        }

        logger.info("sedna_cancel_reservation", source_id=source_id)

        response = await self.client.post(url, params=params)
        response.raise_for_status()
        data = response.json()

        return SednaApiResponse(
            ErrorType=data.get("ErrorType", 0),
            Message=data.get("Message"),
            RecId=data.get("RecId"),
        )

    # =========================================================================
    # Stop Sales
    # =========================================================================

    async def get_stop_sales(self, filter: StopSaleFilter) -> list[SednaStopSale]:
        """
        Get stop sale list.

        Args:
            filter: StopSaleFilter object

        Returns:
            List of SednaStopSale objects
        """
        url = f"{self.base_url}/Integratiion/GetStopSaleList"
        params = filter.model_dump(exclude_none=True)

        logger.debug("sedna_get_stop_sales", filter=params)

        response = await self.client.post(url, params=params)
        response.raise_for_status()
        data = response.json()

        stop_sales = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            stop_sales.append(
                SednaStopSale(
                    RecId=item.get("RecId"),
                    HotelId=item.get("HotelId", 0),
                    HotelName=item.get("HotelName"),
                    BeginDate=item.get("BeginDate", ""),
                    EndDate=item.get("EndDate", ""),
                    RoomTypeId=item.get("RoomTypeId"),
                    RoomTypeName=item.get("RoomTypeName"),
                    BoardId=item.get("BoardId"),
                    BoardName=item.get("BoardName"),
                    IsClose=item.get("IsClose", True),
                    RecordDate=item.get("RecordDate"),
                    UpdateDate=item.get("UpdateDate"),
                )
            )

        logger.info("sedna_stop_sales_found", count=len(stop_sales))
        return stop_sales

    async def get_stop_sales_with_update_date(
        self,
        filter: StopSaleFilter,
    ) -> list[SednaStopSale]:
        """
        Get stop sale list with update date info.

        Args:
            filter: StopSaleFilter object

        Returns:
            List of SednaStopSale objects
        """
        url = f"{self.base_url}/Integratiion/GetStopSaleListWithUpdateDate"
        params = filter.model_dump(exclude_none=True)

        response = await self.client.post(url, params=params)
        response.raise_for_status()
        data = response.json()

        stop_sales = []
        for item in data if isinstance(data, list) else data.get("Data", []):
            stop_sales.append(
                SednaStopSale(
                    RecId=item.get("RecId"),
                    HotelId=item.get("HotelId", 0),
                    HotelName=item.get("HotelName"),
                    BeginDate=item.get("BeginDate", ""),
                    EndDate=item.get("EndDate", ""),
                    RoomTypeId=item.get("RoomTypeId"),
                    RoomTypeName=item.get("RoomTypeName"),
                    BoardId=item.get("BoardId"),
                    BoardName=item.get("BoardName"),
                    IsClose=item.get("IsClose", True),
                    RecordDate=item.get("RecordDate"),
                    UpdateDate=item.get("UpdateDate"),
                )
            )

        return stop_sales

    # =========================================================================
    # Contracts & Packages
    # =========================================================================

    async def get_contracts(
        self,
        hotel_id: int = 0,
        is_active: bool = True,
        use_combine_package: bool = True,
    ) -> list[dict]:
        """Get contract list."""
        url = f"{self.base_url}/Integratiion/GetContractList"
        payload = {
            "RecId": 0,
            "HotelId": hotel_id,
            "RegionId": 0,
            "IsActive": is_active,
            "SeasonId": 0,
            "SaleType": 1,
            "UseCombinePackage": use_combine_package,
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        return data if isinstance(data, list) else data.get("Data", [])

    async def get_quota(
        self,
        hotel_id: int,
        stay_date: str,
        operator_id: int | None = None,
    ) -> dict:
        """
        Get quota for a specific date.

        Args:
            hotel_id: Hotel ID
            stay_date: Stay date (YYYY-MM-DD)
            operator_id: Optional operator ID

        Returns:
            Quota data dict
        """
        url = f"{self.base_url}/Integratiion/GetQuota"
        params = {
            "stayDate": stay_date,
            "operatorId": operator_id or self.operator_id,
            "hotelId": hotel_id,
        }

        response = await self.client.post(url, params=params)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Price Search
    # =========================================================================

    async def hotel_price_search(
        self,
        hotel_id: int,
        begin_date: str,
        end_date: str,
        pax: int,
        childs: int = 0,
        child_info: list[int] | None = None,
        room_type_id: int = 0,
        board_code: str = "0",
        sale_date: str | None = None,
        operator_id: int | None = None,
    ) -> list[dict]:
        """
        Search hotel prices.

        Args:
            hotel_id: Hotel ID
            begin_date: Check-in date (YYYY-MM-DD)
            end_date: Check-out date (YYYY-MM-DD)
            pax: Number of adults
            childs: Number of children
            child_info: List of child ages
            room_type_id: Room type ID (0 = all)
            board_code: Board code (0 = all)
            sale_date: Sale date (YYYY-MM-DD)
            operator_id: Operator ID

        Returns:
            List of price results
        """
        url = f"{self.base_url}/Integratiion/HotelPriceSearch"
        payload = {
            "operatorId": operator_id or self.operator_id,
            "RegionId": 0,
            "BeginDate": begin_date,
            "EndDate": end_date,
            "HotelId": str(hotel_id),
            "Pax": str(pax),
            "Childs": str(childs),
            "ChildInfo": child_info or [],
            "RemainderQuotaCheck": True,
            "SaleDate": sale_date or begin_date,
            "IsAvailable": False,
            "RoomTypeId": str(room_type_id),
            "SubregionId": 0,
            "BoardCode": board_code,
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        return data if isinstance(data, list) else data.get("Data", [])
