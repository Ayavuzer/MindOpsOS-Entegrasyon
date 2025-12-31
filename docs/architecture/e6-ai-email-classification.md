# E6: AI Email Classification & Extraction - Architecture

> **Epic:** E6
> **Tarih:** 2025-12-29
> **Status:** Ready for Development

---

## 📋 Overview

Bu döküman E6 epic'inin teknik implementasyon detaylarını içerir.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI EMAIL PROCESSING PIPELINE                      │
└─────────────────────────────────────────────────────────────────────────┘

     ┌──────────────┐
     │  RAW EMAIL   │
     │ (subject,    │
     │  body_text)  │
     └──────┬───────┘
            │
            ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                      EmailParserService                          │
     │  ┌────────────────────────────────────────────────────────────┐  │
     │  │  1. Check if AI enabled (gemini_api_key exists)            │  │
     │  │  2. If yes → AIEmailParser                                 │  │
     │  │  3. If no or fails → RegexParser (fallback)                │  │
     │  └────────────────────────────────────────────────────────────┘  │
     └──────────────────────────────────────────────────────────────────┘
            │
            ├─── AI Path ────────────────────────────────────────────┐
            │                                                         │
            ▼                                                         │
     ┌──────────────────────────────────────────────────────────────┐ │
     │                    AIEmailParser                              │ │
     │  ┌─────────────────────────────────────────────────────────┐ │ │
     │  │  Step 1: EmailClassifier                                │ │ │
     │  │  ────────────────────────                               │ │ │
     │  │  Input: subject + body[:2000]                           │ │ │
     │  │  Output: EmailClassification {                          │ │ │
     │  │      email_type: "stop_sale" | "reservation" | "other"  │ │ │
     │  │      confidence: 0.0-1.0                                │ │ │
     │  │      language: "tr" | "en" | "ru" | ...                 │ │ │
     │  │  }                                                      │ │ │
     │  └─────────────────────────────────────────────────────────┘ │ │
     │                         │                                     │ │
     │                         ▼                                     │ │
     │  ┌─────────────────────────────────────────────────────────┐ │ │
     │  │  Step 2: Extractor (based on type)                      │ │ │
     │  │  ─────────────────────────────────                      │ │ │
     │  │  if stop_sale:  → StopSaleExtractor                     │ │ │
     │  │  if reservation: → ReservationExtractor                 │ │ │
     │  │                                                         │ │ │
     │  │  Output: StopSaleExtraction | ReservationExtraction     │ │ │
     │  └─────────────────────────────────────────────────────────┘ │ │
     │                         │                                     │ │
     │                         ▼                                     │ │
     │  ┌─────────────────────────────────────────────────────────┐ │ │
     │  │  Step 3: Confidence Check                               │ │ │
     │  │  ─────────────────────────                              │ │ │
     │  │  if confidence >= 0.85: return result                   │ │ │
     │  │  else: fallback to regex                                │ │ │
     │  └─────────────────────────────────────────────────────────┘ │ │
     └──────────────────────────────────────────────────────────────┘ │
            │                                                         │
            │                                                         │
            ├─── Regex Path (Fallback) ──────────────────────────────┘
            │
            ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                         Database                                  │
     │  ┌──────────────────┐     ┌────────────────────────────────────┐ │
     │  │   stop_sales     │     │          reservations              │ │
     │  │  - hotel_name    │     │  - voucher_no                      │ │
     │  │  - date_from     │     │  - hotel_name                      │ │
     │  │  - date_to       │     │  - check_in / check_out            │ │
     │  │  - room_type     │     │  - guests                          │ │
     │  │  - ai_confidence │     │  - ai_confidence                   │ │
     │  └──────────────────┘     └────────────────────────────────────┘ │
     └──────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
apps/api/ai/
├── __init__.py              # Module exports
├── models.py                # Pydantic models
├── client.py                # Gemini client wrapper
├── prompts.py               # System prompts
├── classifier.py            # EmailClassifier service
├── extractors/
│   ├── __init__.py
│   ├── stop_sale.py         # StopSaleExtractor
│   └── reservation.py       # ReservationExtractor
└── parser.py                # AIEmailParser (orchestrator)
```

---

## 📐 Pydantic Models

### models.py

```python
from pydantic import BaseModel, Field
from datetime import date
from typing import Literal, Optional
from decimal import Decimal


class EmailClassification(BaseModel):
    """Email classification result."""
    
    email_type: Literal["stop_sale", "reservation", "other"]
    confidence: float = Field(ge=0, le=1)
    language: str = Field(description="ISO 639-1: tr, en, ru, de, uk")
    reasoning: str = Field(description="Classification explanation")


class StopSaleExtraction(BaseModel):
    """Stop sale email extraction result."""
    
    hotel_name: str = Field(description="Hotel name without suffix")
    date_from: date = Field(description="Stop sale start date")
    date_to: date = Field(description="Stop sale end date")
    room_types: list[str] = Field(
        default_factory=list,
        description="Room type codes. Empty = all rooms"
    )
    board_types: list[str] = Field(
        default_factory=list,
        description="Board type codes. Empty = all"
    )
    is_close: bool = Field(
        default=True,
        description="True=stop sale, False=open sale"
    )
    reason: Optional[str] = Field(default=None)
    extraction_confidence: float = Field(ge=0, le=1)


class Guest(BaseModel):
    """Guest information."""
    
    title: Literal["Mr", "Mrs", "Ms", "Chd", "Inf"] = "Mr"
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    nationality: Optional[str] = None


class ReservationExtraction(BaseModel):
    """Reservation extraction result."""
    
    voucher_no: str = Field(description="Voucher/booking reference")
    hotel_name: str = Field(description="Hotel name")
    check_in: date
    check_out: date
    room_type: str = Field(default="DBL")
    room_type_name: Optional[str] = None
    board_type: str = Field(default="AI")
    adults: int = Field(default=2, ge=1)
    children: int = Field(default=0, ge=0)
    guests: list[Guest] = Field(default_factory=list)
    total_price: Optional[Decimal] = None
    currency: str = Field(default="EUR")
    extraction_confidence: float = Field(ge=0, le=1)
```

---

## 🔧 Gemini Client

### client.py

```python
from google import genai
from google.genai import types
from typing import Type, TypeVar
from pydantic import BaseModel
import os

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Wrapper for Gemini API with structured output support."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash-preview-05-20"
    
    async def extract(
        self,
        prompt: str,
        response_model: Type[T],
        temperature: float = 0.1,
    ) -> T:
        """
        Generate structured output using Gemini.
        
        Args:
            prompt: The prompt text
            response_model: Pydantic model for response schema
            temperature: Creativity (0.0-1.0, lower = more deterministic)
            
        Returns:
            Validated Pydantic model instance
        """
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_model,
                temperature=temperature,
            ),
        )
        
        return response_model.model_validate_json(response.text)
```

---

## 📝 System Prompts

### prompts.py

```python
CLASSIFICATION_PROMPT = """
You are an email classification expert for the tourism/hospitality industry.
Analyze this email and classify it into one of these categories:

1. stop_sale: Hotel announcing that rooms are closed for sale for certain dates
2. reservation: Booking confirmation, voucher, or reservation details
3. other: Any other email type (newsletter, marketing, general inquiry)

Important clues:
- stop_sale keywords: "stop sale", "satış kapatma", "стоп-продажа", "closed for sale"
- reservation keywords: "voucher", "booking", "reservation", "confirmation", "rezervasyon"

Email Subject: {subject}
Email Body:
{body}

Respond with a JSON object matching the schema.
Be confident in your classification.
"""

STOP_SALE_EXTRACTION_PROMPT = """
Extract stop sale information from this hotel email.
The email announces that a hotel is closing/opening room sales for specific dates.

Guidelines:
- hotel_name: Extract full hotel name, remove "Hotel", "Resort" suffix if at the end
- date_from: Start date of stop sale period. Parse any format (DD.MM.YY, YYYY-MM-DD, etc.)
- date_to: End date of stop sale period
- room_types: Extract room codes like DBL, SGL, TRP, FAM. If "all rooms" or not specified, leave empty []
- is_close: True for "stop sale", False for "open sale" or "release"
- reason: Extract if mentioned (renovation, full, etc.)

If you cannot find a required field, make your best guess based on context.
Date from email: {email_date}

Email Subject: {subject}
Email Body:
{body}

Respond with a JSON object matching the schema.
"""

RESERVATION_EXTRACTION_PROMPT = """
Extract reservation/booking information from this document.
This is a hotel booking confirmation or voucher.

Guidelines:
- voucher_no: Look for "Voucher", "Booking", "Reference", "Confirmation" number
- hotel_name: Full hotel name
- check_in/check_out: Parse dates in any format
- room_type: Extract code (DBL=Double, SGL=Single, TRP=Triple, FAM=Family, SUI=Suite)
- board_type: AI=All Inclusive, FB=Full Board, HB=Half Board, BB=B&B, RO=Room Only
- guests: Extract guest names with titles (Mr, Mrs, Chd for child)
- total_price: Extract amount and currency

Email/PDF Content:
{content}

Respond with a JSON object matching the schema.
"""
```

---

## 🔄 Integration Pattern

### parser.py (Orchestrator)

```python
from dataclasses import dataclass
from typing import Optional
from ai.client import GeminiClient
from ai.models import EmailClassification, StopSaleExtraction
from ai.prompts import CLASSIFICATION_PROMPT, STOP_SALE_EXTRACTION_PROMPT


@dataclass
class AIParseResult:
    """Result of AI parsing."""
    
    success: bool
    classification: Optional[EmailClassification] = None
    extraction: Optional[StopSaleExtraction] = None
    error: Optional[str] = None


class AIEmailParser:
    """AI-powered email parser using Gemini."""
    
    def __init__(self, api_key: str):
        self.client = GeminiClient(api_key)
        self.confidence_threshold = 0.85
    
    async def parse(
        self,
        subject: str,
        body: str,
        email_date: str | None = None,
    ) -> AIParseResult:
        """
        Parse email using AI.
        
        Returns:
            AIParseResult with classification and extraction
        """
        try:
            # Step 1: Classify email
            classification = await self.client.extract(
                prompt=CLASSIFICATION_PROMPT.format(
                    subject=subject,
                    body=body[:2000],  # Limit for efficiency
                ),
                response_model=EmailClassification,
            )
            
            # Check confidence
            if classification.confidence < self.confidence_threshold:
                return AIParseResult(
                    success=False,
                    classification=classification,
                    error=f"Low confidence: {classification.confidence}",
                )
            
            # Step 2: Extract based on type
            extraction = None
            if classification.email_type == "stop_sale":
                extraction = await self.client.extract(
                    prompt=STOP_SALE_EXTRACTION_PROMPT.format(
                        subject=subject,
                        body=body,
                        email_date=email_date or "unknown",
                    ),
                    response_model=StopSaleExtraction,
                )
            
            return AIParseResult(
                success=True,
                classification=classification,
                extraction=extraction,
            )
            
        except Exception as e:
            return AIParseResult(
                success=False,
                error=str(e),
            )
```

---

## 📊 Database Changes

### Migration

```sql
-- Add AI confidence columns
ALTER TABLE stop_sales 
ADD COLUMN ai_confidence DECIMAL(3,2),
ADD COLUMN ai_parsed BOOLEAN DEFAULT FALSE;

ALTER TABLE reservations
ADD COLUMN ai_confidence DECIMAL(3,2),
ADD COLUMN ai_parsed BOOLEAN DEFAULT FALSE;

-- Add Gemini API key to tenant settings
ALTER TABLE tenant_settings
ADD COLUMN gemini_api_key_encrypted TEXT;
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
import pytest
from ai.models import EmailClassification, StopSaleExtraction

def test_classification_model():
    data = {
        "email_type": "stop_sale",
        "confidence": 0.95,
        "language": "en",
        "reasoning": "Contains stop sale keywords"
    }
    result = EmailClassification.model_validate(data)
    assert result.email_type == "stop_sale"

def test_stop_sale_extraction_defaults():
    data = {
        "hotel_name": "Grand Resort",
        "date_from": "2025-04-15",
        "date_to": "2025-04-20",
        "extraction_confidence": 0.92
    }
    result = StopSaleExtraction.model_validate(data)
    assert result.is_close == True  # Default
    assert result.room_types == []  # Default (all rooms)
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_ai_parser_stop_sale():
    parser = AIEmailParser(api_key="test-key")
    result = await parser.parse(
        subject="STOP SALE - Mandarin Resort",
        body="Dear Partner, stop sale all rooms (15.04.25 - 20.04.25)",
    )
    
    assert result.success
    assert result.classification.email_type == "stop_sale"
    assert result.extraction.hotel_name == "Mandarin"
```

---

## ⚙️ Configuration

### requirements.txt

```
# AI Dependencies
google-genai>=0.5.0
pydantic>=2.0
```

### Environment Variables

```bash
# Optional global key
GEMINI_API_KEY=your-api-key

# Per-tenant configuration in tenant_settings table
# gemini_api_key_encrypted column
```

---

## 📈 Monitoring & Observability

### Logging

```python
logger.info(
    "ai_classification",
    email_id=email_id,
    email_type=classification.email_type,
    confidence=classification.confidence,
    language=classification.language,
)

logger.info(
    "ai_extraction",
    email_id=email_id,
    extraction_type="stop_sale",
    confidence=extraction.extraction_confidence,
    hotel=extraction.hotel_name,
)
```

### Metrics (Future)

- AI parse success rate
- Average confidence scores
- Fallback trigger rate
- API latency

---

## ✅ Definition of Done

- [ ] E6.S1: AI module created (`apps/api/ai/`)
- [ ] E6.S2: Email classifier working
- [ ] E6.S3: Stop sale extractor working
- [ ] E6.S4: Integration with EmailParserService
- [ ] Database migration applied
- [ ] Unit tests passing
- [ ] Integration test: Parse real email successfully
- [ ] Deployed to production

---

*Architecture document created: 2025-12-29*
