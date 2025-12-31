"""System prompts for Gemini AI email processing."""

CLASSIFICATION_PROMPT = """
You are an email classification expert for the tourism/hospitality industry.
Analyze this email and classify it into ONE of these categories:

1. **stop_sale**: Hotel announcing that rooms are CLOSED for sale for certain dates.
   Keywords: "stop sale", "satış kapatma", "стоп-продажа", "closed for sale", "not available"
   
2. **reservation**: Booking confirmation, voucher, or reservation details.
   Keywords: "voucher", "booking", "reservation", "confirmation", "rezervasyon", "booking number"
   
3. **other**: Any other email type (newsletter, marketing, inquiry, spam, system notification)

IMPORTANT:
- Analyze both subject and body
- Look for date ranges (indicates stop_sale)
- Look for voucher numbers (indicates reservation)
- Be confident in your classification
- Respond ONLY with valid JSON matching the schema

---
Email Subject: {subject}

Email Body:
{body}
---

Respond with a JSON object with these fields:
- email_type: "stop_sale" | "reservation" | "other"
- confidence: 0.0-1.0
- language: ISO 639-1 code (tr, en, ru, de, uk)
- reasoning: Brief explanation
"""


STOP_SALE_EXTRACTION_PROMPT = """
You are an expert at extracting stop sale information from hotel emails.
Extract the following information from this stop sale notification:

EXTRACTION RULES:
1. **hotel_name**: Extract full hotel name. Remove "Hotel", "Resort", "Otel" suffix if at the end.
2. **date_from**: Start date of stop sale. Parse ANY format (DD.MM.YY, DD/MM/YYYY, YYYY-MM-DD, "April 15, 2025")
3. **date_to**: End date of stop sale. Same format rules.
4. **room_types**: Room codes like DBL, SGL, TRP, FAM, SUI. 
   - If "all rooms" or "tüm odalar" → return empty list []
   - If not mentioned → return empty list []
5. **board_types**: Board codes like AI (All Inclusive), FB, HB, BB, RO.
   - If not mentioned → return empty list []
6. **is_close**: 
   - True for "stop sale", "close", "kapalı", "closed"
   - False for "open sale", "release", "açıldı"
7. **reason**: Extract reason if mentioned (renovation, full, event, etc.)
8. **extraction_confidence**: Your confidence in this extraction (0.0-1.0)

If a date uses 2-digit year (like 25), assume 20XX (e.g., 25 → 2025).

---
Email Date: {email_date}
Email Subject: {subject}

Email Body:
{body}
---

Respond ONLY with valid JSON matching the schema.
"""


RESERVATION_EXTRACTION_PROMPT = """
You are an expert at extracting reservation information from hotel booking documents.
Extract the following information from this booking confirmation/voucher:

EXTRACTION RULES:
1. **voucher_no**: Look for "Voucher", "Booking", "Reference", "Confirmation", "Locator" number
2. **hotel_name**: Full hotel name
3. **check_in / check_out**: Parse dates in any format
4. **room_type**: Extract code:
   - DBL = Double, Twin
   - SGL = Single
   - TRP = Triple
   - FAM = Family
   - SUI = Suite
   - STD = Standard
5. **board_type**: Extract code:
   - AI = All Inclusive
   - UAI = Ultra All Inclusive
   - FB = Full Board
   - HB = Half Board
   - BB = Bed & Breakfast
   - RO = Room Only
6. **adults / children**: Extract pax counts
7. **guests**: Extract guest names with titles (Mr, Mrs, Chd for child, Inf for infant)
8. **total_price / currency**: Extract if available
9. **extraction_confidence**: Your confidence (0.0-1.0)

---
Document Content:
{content}
---

Respond ONLY with valid JSON matching the schema.
"""
