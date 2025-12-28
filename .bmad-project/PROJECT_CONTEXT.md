# MindOpsOS-Entegrasyon - Project Context

> **Project ID:** mindops-entegrasyon  
> **Created:** 2025-12-27  
> **Status:** New  
> **Type:** Backend Integration Service

---

## 🎯 Mission

Juniper otel rezervasyon sistemi ile Sedna Agency programı arasında otomatik entegrasyon sağlayan servis. Email üzerinden gelen rezervasyon PDF'lerini ve stop sale bildirimlerini okuyup Sedna API'sine aktarır.

---

## 🏗️ Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    MindOpsOS-Entegrasyon                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Email      │  │   Email     │  │   Sedna     │             │
│  │  Listener   │→ │   Parser    │→ │   Client    │             │
│  │  (IMAP)     │  │   (PDF/Text)│  │   (API)     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│        ↓                ↓                ↓                      │
│  ┌─────────────────────────────────────────────────┐           │
│  │              Reservation Service                 │           │
│  │  • Parse Juniper PDF confirmations              │           │
│  │  • Extract booking details                      │           │
│  │  • Push to Sedna /InsertReservation             │           │
│  └─────────────────────────────────────────────────┘           │
│  ┌─────────────────────────────────────────────────┐           │
│  │              Stop Sale Service                   │           │
│  │  • Parse hotel stop sale notifications          │           │
│  │  • Extract date ranges + room types             │           │
│  │  • Push to Sedna API                            │           │
│  └─────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| **Runtime** | Python 3.12 |
| **Email** | imaplib / aiosmtplib |
| **PDF Parsing** | PyMuPDF (fitz) / pdfplumber |
| **HTTP Client** | httpx / aiohttp |
| **Scheduling** | APScheduler |
| **Data Validation** | Pydantic v2 |
| **Logging** | structlog |
| **Config** | python-dotenv |
| **Testing** | pytest + pytest-asyncio |

---

## 📧 Email Configuration

### Booking Emails

- **Address:** <booking@pointholiday.com>
- **Purpose:** Juniper reservation confirmations (PDF attachments)
- **Content:** Reservation details, guest info, room types, dates

### Stop Sale Emails  

- **Address:** <stopsale@pointholiday.com>
- **Purpose:** Hotel stop sale notifications
- **Content:** Date ranges, room types, board types

---

## 🌐 Sedna Agency API

- **Base URL:** <https://test.kodsedna.com/api/Integration>
- **Auth:** Cookie-based (username/password login)
- **Format:** JSON

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/AgencyLogin` | GET | Authenticate and get OperatorId |
| `/InsertReservation` | POST | Create new booking |
| `/GetReservations` | POST | List reservations |
| `/CancelReservation` | POST | Cancel booking |
| `/GetStopSaleList` | POST | Retrieve stop sales |
| `/GetHotelList` | GET | Get hotel definitions |
| `/GetRoomTypeList` | GET | Get room type definitions |

---

## 📁 Source Tree

```
MindOpsOS-Entegrasyon/
├── .bmad-project/
│   ├── PROJECT_CONTEXT.md      # This file
│   └── memory/
│       └── project-state.md    # Current state
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration loader
│   ├── services/
│   │   ├── email_service.py    # IMAP connection, email fetching
│   │   ├── sedna_client.py     # Sedna API client
│   │   ├── reservation_service.py  # Booking processing
│   │   └── stopsale_service.py     # Stop sale processing
│   ├── parsers/
│   │   ├── pdf_parser.py       # PDF extraction
│   │   ├── email_parser.py     # Email body parsing
│   │   └── juniper_parser.py   # Juniper-specific formats
│   ├── models/
│   │   ├── reservation.py      # Pydantic models
│   │   ├── stopsale.py
│   │   └── sedna_types.py      # Sedna API types
│   └── utils/
│       ├── logger.py
│       └── date_utils.py
├── config/
│   ├── .env.example
│   └── settings.yaml
├── docs/
│   ├── prd/
│   │   └── main-prd.md
│   ├── architecture/
│   └── stories/
├── tests/
│   ├── test_parsers/
│   ├── test_services/
│   └── fixtures/
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 🚀 Quick Start

```bash
# Clone and setup
cd /Users/aliyavuzer/MindOpsOS-Entegrasyon

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example config/.env
# Edit .env with credentials

# Run service
python -m src.main
```

---

## 📋 Current Status

| Component | Status |
|-----------|--------|
| Project Structure | ✅ Created |
| PRD | 🔄 In Progress |
| Requirements.txt | ⏳ Pending |
| Email Service | ⏳ Pending |
| PDF Parser | ⏳ Pending |
| Sedna Client | ⏳ Pending |
| Reservation Service | ⏳ Pending |
| Stop Sale Service | ⏳ Pending |

---

## ⚠️ Security Notes

- Email credentials stored in `.env` (not committed)
- Sedna API credentials in environment variables
- All sensitive data excluded from version control

---

*Created by Antigravity Agent - 2025-12-27*
