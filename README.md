# MindOpsOS Entegrasyon

> Multi-Tenant Juniper → Sedna Integration Platform

## 🚀 Overview

A full-stack SaaS platform that automates the integration between Juniper Travel Technology and Sedna Agency systems. Originally built for Point Holiday, now evolved into a multi-tenant platform.

## 📊 Stats

| Metric | Value |
|--------|-------|
| Stories Completed | 14 |
| Story Points | 47 |
| API Endpoints | 22 |
| Frontend Pages | 8 |
| Database Tables | 9 |
| Lines of Code | ~8000 |

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Next.js 14    │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   Frontend      │     │   Backend       │     │   + asyncpg     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       ▼
        │               ┌─────────────────┐
        │               │  External APIs  │
        │               │  - POP3 Email   │
        │               │  - Sedna API    │
        │               └─────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│            Frontend Pages               │
│  Dashboard │ Login │ Register │ Settings│
│  Emails │ Reservations │ Stop Sales     │
│  History                                │
└─────────────────────────────────────────┘
```

## 📦 Modules

### Backend (FastAPI)

| Module | Description | Endpoints |
|--------|-------------|-----------|
| `auth` | JWT authentication | `/api/auth/*` |
| `tenant` | Settings & encryption | `/api/tenant/*` |
| `emailfetch` | POP3 email ingestion | `/api/email/*` |
| `sedna` | Sedna API sync | `/api/sedna/*` |
| `processing` | Pipeline orchestration | `/api/processing/*` |

### Frontend (Next.js)

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | Stats + Run Pipeline |
| Login | `/login` | JWT authentication |
| Register | `/register` | Tenant creation |
| Settings | `/settings` | Credentials config |
| Emails | `/emails` | Email list + filters |
| Reservations | `/reservations` | Reservation cards |
| Stop Sales | `/stop-sales` | Stop sale list |
| History | `/history` | Pipeline run history |

## 🔄 Processing Pipeline

```
POST /api/processing/run
    │
    ├─→ 1️⃣ FETCH Booking Emails (POP3)
    │
    ├─→ 2️⃣ FETCH Stop Sale Emails (POP3)
    │
    ├─→ 3️⃣ PARSE Pending Emails
    │       ├─→ PDF → JuniperPdfParser → Reservation
    │       └─→ Body → StopSaleEmailParser → Stop Sale
    │
    ├─→ 4️⃣ SYNC Pending to Sedna
    │
    └─→ Return Combined Results
```

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `tenants` | Tenant companies |
| `users` | Users per tenant |
| `sessions` | JWT sessions |
| `tenant_settings` | Encrypted credentials |
| `emails` | Fetched emails |
| `reservations` | Parsed reservations |
| `stop_sales` | Parsed stop sales |
| `processing_logs` | Email processing logs |
| `pipeline_runs` | Pipeline run history |

## 🔐 Security

- **JWT Authentication** - Secure token-based auth
- **Fernet Encryption** - Credentials encrypted at rest
- **Tenant Isolation** - Data separated by tenant_id
- **Password Hashing** - bcrypt with salt

## 🚀 Quick Start

### Backend

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Database

```bash
# Run migrations
psql -U aria -d mindops_entegrasyon -f migrations/001_create_tenants.sql
# ... etc
```

## 📚 API Documentation

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- Health Check: `http://localhost:8080/health`

## 📁 Project Structure

```
MindOpsOS-Entegrasyon/
├── apps/
│   ├── api/                 # FastAPI backend
│   │   ├── auth/            # Authentication module
│   │   ├── tenant/          # Tenant settings
│   │   ├── emailfetch/      # POP3 + parsing
│   │   ├── sedna/           # Sedna integration
│   │   ├── processing/      # Pipeline orchestration
│   │   └── main.py          # App entrypoint
│   └── web/                 # Next.js frontend
├── src/                     # Legacy/shared code
│   ├── parsers/             # PDF & email parsers
│   └── services/            # Core services
├── migrations/              # SQL migrations
└── docs/
    ├── stories/             # User stories
    └── architecture/        # Design docs
```

## 👨‍💻 Development

Built with BMad methodology using Antigravity AI agent.

### Tech Stack

- **Backend**: Python 3.11, FastAPI, asyncpg, Pydantic
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Database**: PostgreSQL 17
- **Auth**: JWT, bcrypt, Fernet encryption

## 📝 License

Private - Point Holiday / MindOps

---

Built with ❤️ by Antigravity Agent
