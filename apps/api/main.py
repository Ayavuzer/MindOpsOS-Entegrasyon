"""FastAPI backend for MindOpsOS Entegrasyon Admin Panel."""

from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncpg

# Auth module
from auth import router as auth_router, set_auth_service, AuthService, get_optional_user, UserResponse

# Tenant module
from tenant import router as tenant_router, set_settings_service, TenantSettingsService

# Email module
from emailfetch import router as email_router, set_email_service, TenantEmailService

# Sedna module
from sedna import router as sedna_router, set_sedna_service, TenantSednaService

# Processing module
from processing import router as processing_router, set_processing_service, ProcessingService

# =============================================================================
# Configuration
# =============================================================================

DATABASE_URL = "postgresql://aria:aria_secure_2024@localhost:5432/mindops_entegrasyon"

pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    print("✅ Database connected")
    
    # Initialize auth service
    auth_service = AuthService(pool)
    set_auth_service(auth_service)
    print("✅ Auth service initialized")
    
    # Initialize tenant settings service
    settings_service = TenantSettingsService(pool)
    set_settings_service(settings_service)
    print("✅ Tenant settings service initialized")
    
    # Initialize email service
    email_service = TenantEmailService(pool, settings_service)
    set_email_service(email_service)
    print("✅ Email service initialized")
    
    # Initialize sedna service
    sedna_service = TenantSednaService(pool, settings_service)
    set_sedna_service(sedna_service)
    print("✅ Sedna service initialized")
    
    # Initialize processing service
    processing_service = ProcessingService(pool, email_service, sedna_service)
    set_processing_service(processing_service)
    print("✅ Processing service initialized")
    
    yield
    await pool.close()
    print("👋 Database disconnected")


app = FastAPI(
    title="MindOpsOS Entegrasyon API",
    description="""
## Multi-Tenant Juniper → Sedna Integration Platform

This API provides:
- 🔐 **Authentication** - JWT-based multi-tenant auth
- ⚙️ **Tenant Settings** - Encrypted credential storage
- 📧 **Email Fetch** - POP3 email ingestion
- 📝 **Email Parsing** - PDF and text parsing
- 🔄 **Sedna Sync** - Reservation and stop sale sync
- ⚡ **Processing Pipeline** - One-click automation

### Authentication
All protected endpoints require a Bearer token in the Authorization header.
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        - status: "healthy" or "unhealthy"
        - database: connection status
        - version: API version
    """
    db_status = "connected"
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "version": "1.0.0",
        "services": {
            "auth": "initialized",
            "tenant_settings": "initialized",
            "email_fetch": "initialized",
            "sedna_sync": "initialized",
            "processing": "initialized",
        }
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API information."""
    return {
        "name": "MindOpsOS Entegrasyon API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health",
    }


# Include auth router
app.include_router(auth_router)

# Include tenant settings router
app.include_router(tenant_router)

# Include email router
app.include_router(email_router)

# Include sedna router
app.include_router(sedna_router)

# Include processing router
app.include_router(processing_router)
# =============================================================================
# Models
# =============================================================================


class StatsResponse(BaseModel):
    total_emails: int
    emails_today: int
    pending_emails: int
    processed_emails: int
    failed_emails: int
    total_reservations: int
    total_stop_sales: int
    success_rate: float


class EmailSummary(BaseModel):
    id: int
    subject: str
    sender: str
    received_at: datetime
    email_type: str
    status: str
    has_pdf: bool
    voucher_no: Optional[str] = None


class EmailDetail(BaseModel):
    id: int
    message_id: str
    subject: str
    sender: str
    recipients: list[str]
    received_at: datetime
    body_text: str
    email_type: str
    status: str
    has_pdf: bool
    pdf_filename: Optional[str] = None
    voucher_no: Optional[str] = None
    sedna_rec_id: Optional[int] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


class ReservationSummary(BaseModel):
    id: int
    voucher_no: str
    hotel_name: str
    check_in: datetime
    check_out: datetime
    adults: int
    children: int
    status: str
    sedna_synced: bool
    created_at: datetime


class StopSaleSummary(BaseModel):
    id: int
    hotel_name: str
    date_from: datetime
    date_to: datetime
    is_close: bool
    reason: Optional[str] = None
    sedna_synced: bool
    created_at: datetime


class ConnectionTestResult(BaseModel):
    service: str
    success: bool
    message: str
    details: Optional[dict] = None


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(user: Optional[UserResponse] = Depends(get_optional_user)):
    """Get dashboard statistics (filtered by tenant if authenticated)."""
    async with pool.acquire() as conn:
        # Build tenant filter
        tenant_filter = ""
        tenant_params = []
        if user:
            tenant_filter = " AND tenant_id = $1"
            tenant_params = [user.tenant_id]
        
        # Total emails
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM emails WHERE 1=1{tenant_filter}",
            *tenant_params,
        )
        
        # Today's emails
        if user:
            today = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE created_at >= CURRENT_DATE AND tenant_id = $1",
                user.tenant_id,
            )
        else:
            today = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE created_at >= CURRENT_DATE"
            )
        
        # By status
        if user:
            pending = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'pending' AND tenant_id = $1",
                user.tenant_id,
            )
            processed = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'processed' AND tenant_id = $1",
                user.tenant_id,
            )
            failed = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'failed' AND tenant_id = $1",
                user.tenant_id,
            )
            reservations = await conn.fetchval(
                "SELECT COUNT(*) FROM reservations WHERE tenant_id = $1",
                user.tenant_id,
            )
            stop_sales = await conn.fetchval(
                "SELECT COUNT(*) FROM stop_sales WHERE tenant_id = $1",
                user.tenant_id,
            )
        else:
            pending = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'pending'"
            )
            processed = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'processed'"
            )
            failed = await conn.fetchval(
                "SELECT COUNT(*) FROM emails WHERE status = 'failed'"
            )
            reservations = await conn.fetchval("SELECT COUNT(*) FROM reservations")
            stop_sales = await conn.fetchval("SELECT COUNT(*) FROM stop_sales")
        
        # Success rate
        success_rate = 0.0
        if total > 0:
            success_rate = (processed / total) * 100
        
        return StatsResponse(
            total_emails=total or 0,
            emails_today=today or 0,
            pending_emails=pending or 0,
            processed_emails=processed or 0,
            failed_emails=failed or 0,
            total_reservations=reservations or 0,
            total_stop_sales=stop_sales or 0,
            success_rate=round(success_rate, 2),
        )


@app.get("/api/emails", response_model=list[EmailSummary])
async def get_emails(
    status: Optional[str] = Query(None),
    email_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    user: Optional[UserResponse] = Depends(get_optional_user),
):
    """Get email list with filtering (filtered by tenant if authenticated)."""
    async with pool.acquire() as conn:
        query = """
            SELECT id, subject, sender, received_at, email_type, status, has_pdf, voucher_no
            FROM emails
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        # Tenant filter
        if user:
            param_count += 1
            query += f" AND tenant_id = ${param_count}"
            params.append(user.tenant_id)
        
        if status:
            param_count += 1
            query += f" AND status = ${param_count}"
            params.append(status)
        
        if email_type:
            param_count += 1
            query += f" AND email_type = ${param_count}"
            params.append(email_type)
        
        query += f" ORDER BY received_at DESC LIMIT {limit} OFFSET {offset}"
        
        rows = await conn.fetch(query, *params)
        
        return [
            EmailSummary(
                id=row["id"],
                subject=row["subject"] or "",
                sender=row["sender"] or "",
                received_at=row["received_at"],
                email_type=row["email_type"],
                status=row["status"],
                has_pdf=row["has_pdf"],
                voucher_no=row["voucher_no"],
            )
            for row in rows
        ]


@app.get("/api/emails/{email_id}", response_model=EmailDetail)
async def get_email_detail(email_id: int):
    """Get email details."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM emails WHERE id = $1",
            email_id,
        )
        
        if not row:
            raise HTTPException(404, "Email not found")
        
        return EmailDetail(
            id=row["id"],
            message_id=row["message_id"],
            subject=row["subject"] or "",
            sender=row["sender"] or "",
            recipients=list(row["recipients"]) if row["recipients"] else [],
            received_at=row["received_at"],
            body_text=row["body_text"] or "",
            email_type=row["email_type"],
            status=row["status"],
            has_pdf=row["has_pdf"],
            pdf_filename=row["pdf_filename"],
            voucher_no=row["voucher_no"],
            sedna_rec_id=row["sedna_rec_id"],
            error_message=row["error_message"],
            processed_at=row["processed_at"],
            created_at=row["created_at"],
        )


@app.post("/api/emails/{email_id}/reprocess")
async def reprocess_email(email_id: int):
    """Mark email for reprocessing."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE emails 
            SET status = 'pending', error_message = NULL
            WHERE id = $1
            """,
            email_id,
        )
        return {"success": True, "message": "Email queued for reprocessing"}


@app.get("/api/reservations", response_model=list[ReservationSummary])
async def get_reservations(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    user: Optional[UserResponse] = Depends(get_optional_user),
):
    """Get reservation list (filtered by tenant if authenticated)."""
    async with pool.acquire() as conn:
        query = """
            SELECT id, voucher_no, hotel_name, check_in, check_out, 
                   adults, children, status, sedna_synced, created_at
            FROM reservations
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        # Tenant filter
        if user:
            param_count += 1
            query += f" AND tenant_id = ${param_count}"
            params.append(user.tenant_id)
        
        if status:
            param_count += 1
            query += f" AND status = ${param_count}"
            params.append(status)
        
        query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
        
        rows = await conn.fetch(query, *params)
        
        return [
            ReservationSummary(
                id=row["id"],
                voucher_no=row["voucher_no"],
                hotel_name=row["hotel_name"] or "",
                check_in=row["check_in"],
                check_out=row["check_out"],
                adults=row["adults"],
                children=row["children"],
                status=row["status"],
                sedna_synced=row["sedna_synced"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@app.get("/api/stop-sales", response_model=list[StopSaleSummary])
async def get_stop_sales(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    user: Optional[UserResponse] = Depends(get_optional_user),
):
    """Get stop sale list (filtered by tenant if authenticated)."""
    async with pool.acquire() as conn:
        if user:
            rows = await conn.fetch(
                f"""
                SELECT id, hotel_name, date_from, date_to, is_close, 
                       reason, sedna_synced, created_at
                FROM stop_sales
                WHERE tenant_id = $1
                ORDER BY created_at DESC
                LIMIT {limit} OFFSET {offset}
                """,
                user.tenant_id,
            )
        else:
            rows = await conn.fetch(
                f"""
                SELECT id, hotel_name, date_from, date_to, is_close, 
                       reason, sedna_synced, created_at
                FROM stop_sales
                ORDER BY created_at DESC
                LIMIT {limit} OFFSET {offset}
                """
        )
        
        return [
            StopSaleSummary(
                id=row["id"],
                hotel_name=row["hotel_name"],
                date_from=row["date_from"],
                date_to=row["date_to"],
                is_close=row["is_close"],
                reason=row["reason"],
                sedna_synced=row["sedna_synced"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@app.post("/api/test/database", response_model=ConnectionTestResult)
async def test_database():
    """Test database connection."""
    try:
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            return ConnectionTestResult(
                service="PostgreSQL",
                success=True,
                message="Connected successfully",
                details={"version": version[:50]},
            )
    except Exception as e:
        return ConnectionTestResult(
            service="PostgreSQL",
            success=False,
            message=str(e),
        )


@app.post("/api/test/sedna", response_model=ConnectionTestResult)
async def test_sedna():
    """Test Sedna API connection."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://test.kodsedna.com/SednaAgencyb2bApi/api/Integratiion/AgencyLogin",
                params={"username": "7STAR", "password": "1234"},
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                # Sedna returns ErrorType: 0 for success, RecId for operator ID
                if data.get("ErrorType") == 0 and data.get("RecId"):
                    return ConnectionTestResult(
                        service="Sedna API",
                        success=True,
                        message="Connected successfully",
                        details={"operator_id": data.get("RecId")},
                    )
                else:
                    return ConnectionTestResult(
                        service="Sedna API",
                        success=False,
                        message=data.get("Message", "Login failed"),
                    )
            else:
                return ConnectionTestResult(
                    service="Sedna API",
                    success=False,
                    message=f"HTTP {response.status_code}",
                )
    except Exception as e:
        return ConnectionTestResult(
            service="Sedna API",
            success=False,
            message=str(e),
        )


@app.post("/api/test/pop3", response_model=ConnectionTestResult)
async def test_pop3():
    """Test POP3 connection with Stop Sale email."""
    import poplib
    import ssl
    
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        server = poplib.POP3_SSL(
            "mail.pointholiday.com",
            995,
            context=context,
            timeout=10,
        )
        
        # Stop Sale email credentials
        server.user("stopsale@pointholiday.com")
        server.pass_("Pnt7689hLd?")
        
        num_messages = len(server.list()[1])
        server.quit()
        
        return ConnectionTestResult(
            service="POP3 (Stop Sale)",
            success=True,
            message="Connected successfully",
            details={"message_count": num_messages, "email": "stopsale@pointholiday.com"},
        )
    except Exception as e:
        return ConnectionTestResult(
            service="POP3 (Stop Sale)",
            success=False,
            message=str(e),
        )


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
