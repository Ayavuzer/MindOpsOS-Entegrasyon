# MindOpsOS-Entegrasyon

Juniper rezervasyon sistemi ile Sedna Agency programı arasında otomatik email-tabanlı entegrasyon servisi.

## 🎯 Features

- **Rezervasyon İşleme:** Juniper'dan gelen PDF formatlı rezervasyon onaylarını otomatik parse ve Sedna'ya kayıt
- **Stop Sale İşleme:** Otellerden gelen satış durdurma bildirimlerini otomatik işleme
- **7/24 Otomasyon:** Sürekli email izleme ve anında işlem

## 🚀 Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example config/.env
# Edit .env with your credentials

# Run service
python -m src.main
```

## 📁 Project Structure

```
MindOpsOS-Entegrasyon/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration
│   ├── services/            # Business logic
│   ├── parsers/             # PDF/Email parsing
│   ├── models/              # Data models
│   └── utils/               # Utilities
├── config/
│   └── .env.example
├── docs/
│   └── prd/                 # Product docs
└── tests/
```

## 📧 Email Configuration

| Purpose | Address |
|---------|---------|
| Reservations | <booking@pointholiday.com> |
| Stop Sales | <stopsale@pointholiday.com> |

## 🌐 Sedna API

- **Base URL:** <https://test.kodsedna.com/api/Integration>
- **Docs:** <https://test.kodsedna.com/AgencyDoc/>

## 📊 Status

| Component | Status |
|-----------|--------|
| Project Setup | ✅ |
| Email Service | ⏳ |
| PDF Parser | ⏳ |
| Sedna Client | ⏳ |

---

*Point Holiday - MindOps Integration*
