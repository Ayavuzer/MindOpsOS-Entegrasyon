"""Tests for Sedna client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date

from src.services.sedna_client import (
    SednaClient,
    SednaApiResponse,
    SednaHotel,
    SednaApiError,
    SednaAuthError,
    SednaValidationError,
    ReservationRequest,
    CustomerRequest,
    ReservationFilter,
    StopSaleFilter,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sedna_client():
    """Create a test client."""
    return SednaClient(
        base_url="http://test.kodsedna.com/SednaAgencyb2bApi/api",
        username="7STAR",
        password="1234",
    )


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def sample_reservation():
    """Create a sample reservation request."""
    return ReservationRequest(
        HotelId=18,
        OperatorId=571,
        CheckinDate="2024-09-05",
        CheckOutDate="2024-09-10",
        Adult=2,
        Child=1,
        BoardId=1,
        RoomTypeId=3,
        SaleDate="2024-08-01",
        Customers=[
            CustomerRequest(
                Title="Mr",
                FirstName="JOHN",
                LastName="DOE",
                Age=35,
                Nationality="UKRAINE",
                NationalityId=79,
            ),
            CustomerRequest(
                Title="Mrs",
                FirstName="JANE",
                LastName="DOE",
                Age=33,
            ),
            CustomerRequest(
                Title="Chd",
                FirstName="JUNIOR",
                LastName="DOE",
                Age=5,
                BirthDate="2019-05-15",
            ),
        ],
        HotelRemark="Test reservation",
        ReservationRemark="Imported from Juniper",
    )


# =============================================================================
# Login Tests
# =============================================================================


@pytest.mark.asyncio
async def test_login_success(sedna_client, mock_response):
    """Test successful login."""
    mock_response.json.return_value = {
        "ErrorType": 0,
        "Message": None,
        "RecId": 571,
    }

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)

        operator_id = await sedna_client.login()

        assert operator_id == 571
        assert sedna_client.operator_id == 571
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_login_failure(sedna_client, mock_response):
    """Test login failure."""
    mock_response.json.return_value = {
        "ErrorType": 1,
        "Message": "Invalid credentials",
        "RecId": None,
    }

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(SednaAuthError) as exc_info:
            await sedna_client.login()

        assert "Invalid credentials" in str(exc_info.value)


# =============================================================================
# Hotel Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_hotels(sedna_client, mock_response):
    """Test getting hotel list."""
    mock_response.json.return_value = [
        {"RecId": 18, "Name": "Grand Hotel", "IsActive": True},
        {"RecId": 28, "Name": "Paradise Resort", "IsActive": True},
    ]

    sedna_client.operator_id = 571

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)

        hotels = await sedna_client.get_hotels()

        assert len(hotels) == 2
        assert hotels[0].RecId == 18
        assert hotels[0].Name == "Grand Hotel"


# =============================================================================
# Reservation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_insert_reservation_success(sedna_client, mock_response, sample_reservation):
    """Test successful reservation insertion."""
    mock_response.json.return_value = [{
        "ErrorType": 0,
        "Message": None,
        "RecId": 12345,
    }]

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await sedna_client.insert_reservation(
            reservation=sample_reservation,
            voucher_no="V2024TEST001",
        )

        assert result.ErrorType == 0
        assert result.RecId == 12345


@pytest.mark.asyncio
async def test_insert_reservation_validation_error(sedna_client, mock_response, sample_reservation):
    """Test reservation with validation error."""
    mock_response.json.return_value = [{
        "ErrorType": 99,
        "Message": "Hotel ID not found",
        "RecId": None,
    }]

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(SednaValidationError) as exc_info:
            await sedna_client.insert_reservation(
                reservation=sample_reservation,
                voucher_no="V2024TEST001",
            )

        assert "Hotel ID not found" in str(exc_info.value)
        assert exc_info.value.error_type == 99


@pytest.mark.asyncio
async def test_get_reservations(sedna_client, mock_response):
    """Test getting reservations."""
    mock_response.json.return_value = [
        {"RecId": 1, "VoucherNo": "V001", "HotelId": 18},
        {"RecId": 2, "VoucherNo": "V002", "HotelId": 28},
    ]

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)

        filter = ReservationFilter(OperatorId=571)
        reservations = await sedna_client.get_reservations(filter)

        assert len(reservations) == 2
        assert reservations[0]["VoucherNo"] == "V001"


# =============================================================================
# Stop Sale Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_stop_sales(sedna_client, mock_response):
    """Test getting stop sales."""
    mock_response.json.return_value = [
        {
            "RecId": 1,
            "HotelId": 18,
            "HotelName": "Grand Hotel",
            "BeginDate": "2024-09-01",
            "EndDate": "2024-09-15",
            "IsClose": True,
        },
    ]

    with patch.object(sedna_client, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)

        filter = StopSaleFilter(
            hotelId=18,
            stopDateBegin="2024-09-01",
            stopDateEnd="2024-09-30",
        )
        stop_sales = await sedna_client.get_stop_sales(filter)

        assert len(stop_sales) == 1
        assert stop_sales[0].HotelId == 18
        assert stop_sales[0].IsClose is True


# =============================================================================
# Model Tests
# =============================================================================


def test_reservation_request_serialization(sample_reservation):
    """Test ReservationRequest JSON serialization."""
    data = sample_reservation.model_dump(exclude_none=True)

    assert data["HotelId"] == 18
    assert data["OperatorId"] == 571
    assert data["Adult"] == 2
    assert data["Child"] == 1
    assert len(data["Customers"]) == 3
    assert data["Customers"][0]["Title"] == "Mr"
    assert data["Customers"][0]["FirstName"] == "JOHN"


def test_customer_request_defaults():
    """Test CustomerRequest default values."""
    customer = CustomerRequest(FirstName="TEST", LastName="USER")

    assert customer.Title == "Mr"
    assert customer.IsArrivalTransfer == 0
    assert customer.IsDepartureTransfer == 0


def test_stop_sale_filter():
    """Test StopSaleFilter model."""
    filter = StopSaleFilter(
        hotelId=18,
        stopDateBegin="2024-09-01",
        stopDateEnd="2024-09-30",
    )

    data = filter.model_dump(exclude_none=True)

    assert data["hotelId"] == 18
    assert data["stopDateBegin"] == "2024-09-01"
    assert "recordDateBegin" not in data  # Not set


# =============================================================================
# Integration Test (requires actual API - skipped by default)
# =============================================================================


@pytest.mark.skip(reason="Requires actual Sedna API connection")
@pytest.mark.asyncio
async def test_real_api_connection():
    """Test real API connection (manual test)."""
    async with SednaClient(
        base_url="http://test.kodsedna.com/SednaAgencyb2bApi/api",
        username="7STAR",
        password="7STAR",
    ) as client:
        # Login
        assert client.operator_id == 571

        # Get hotels
        hotels = await client.get_hotels()
        assert len(hotels) > 0

        # Get countries
        countries = await client.get_countries()
        assert len(countries) > 0

        print(f"✅ Connected! Found {len(hotels)} hotels, {len(countries)} countries")
