import re
from typing import Optional, Tuple, Dict, Any

from core.location_utils import normalize_location
from core.tech_grounding import extract_deterministic_tech_stack

# Compiled regular expressions for maximum performance
# Negative patterns to reject company-centric age/experience
RE_YOE_NEGATIVE = re.compile(
    r'(?:(?:company|firm|we|our\s+team|organization|business|group)\s+(?:has|have|had|with)\s+)'
    r'|(?:founded\s+(?:in|over)\s+)'
    r'|(?:serving\s+(?:for|over)\s+)'
    r'|(?:(?:over|more\s+than)\s+\d+\s+years?\s+(?:in\s+the\s+(?:industry|market|business|domain)))',
    re.IGNORECASE
)

# High-confidence: Requirement-anchored patterns
RE_YOE_REQ_RANGE = re.compile(
    r'(?:requires?|requiring|minimum|at\s+least|must\s+have|need|seeking|with|having|candidates?\s+(?:with|having|should\s+have))\s*'
    r'(\d+)\s*(?:-|to|–)\s*(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+(?:experience|exp))?',
    re.IGNORECASE
)
RE_YOE_REQ_PLUS = re.compile(
    r'(?:requires?|requiring|minimum|at\s+least|must\s+have|need|seeking|with|having|candidates?\s+(?:with|having|should\s+have))\s*'
    r'(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)',
    re.IGNORECASE
)
RE_YOE_REQ_MIN = re.compile(
    r'(?:minimum|min|at least)\s*(\d+)\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience|\s+exp)?',
    re.IGNORECASE
)

# Medium-confidence: General patterns (without explicit requirement verbs)
RE_YOE_RANGE = re.compile(
    r'(\d+)\s*(?:-|to|–)\s*(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+(?:experience|exp))',
    re.IGNORECASE
)
RE_YOE_PLUS = re.compile(
    r'(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)',
    re.IGNORECASE
)
RE_YOE_GENERAL = re.compile(
    r'\b(\d+)\+?\s*(?:years?|yrs?)\b(?:\s+of\s+experience|\s+experience|\s+exp\b)',
    re.IGNORECASE
)

# ─── USD Salary Regexes ────────────────────────────────────────────────────────

RE_SALARY_RANGE_K = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\s*(?:-|to|–)\s*(?:\$|USD\s*)?\s*(\d{2,3}(?:\.\d+)?)\s*[kK]',
    re.IGNORECASE
)
RE_SALARY_RANGE_FULL = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3},\d{3})\s*(?:-|to|–)\s*(?:\$|USD\s*)?\s*(\d{2,3},\d{3})',
    re.IGNORECASE
)
RE_SALARY_SINGLE_K = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\s*(?:\/|\s+a\s+|\s+per\s+)?(?:yr|year|annually)?',
    re.IGNORECASE
)
RE_SALARY_SINGLE_FULL = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3},\d{3})\s*(?:\/|\s+a\s+|\s+per\s+)?(?:yr|year|annually)',
    re.IGNORECASE
)
RE_HOURLY_RANGE = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3}(?:\.\d{2})?)\s*(?:-|to|–)\s*(?:\$|USD\s*)?\s*(\d{2,3}(?:\.\d{2})?)\s*(?:\/|\s+per\s+)\s*(?:hr|hour|hourly)',
    re.IGNORECASE
)
RE_HOURLY_SINGLE = re.compile(
    r'(?:\$|USD\s*)\s*(\d{2,3}(?:\.\d{2})?)\s*(?:\/|\s+per\s+)\s*(?:hr|hour|hourly)',
    re.IGNORECASE
)

# ─── INR Salary Regexes ────────────────────────────────────────────────────────

RE_INR_LPA_RANGE = re.compile(
    r'(?:₹|INR|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(?:₹|INR|Rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|p\.?a\.?)|l\s*p\s*a)',
    re.IGNORECASE
)
RE_INR_LPA_SINGLE = re.compile(
    r'(?:₹|INR|Rs\.?)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|p\.?a\.?)|l\s*p\s*a)',
    re.IGNORECASE
)
RE_INR_RANGE_FULL = re.compile(
    r'(?:₹|INR|Rs\.?)\s*(\d{1,3}(?:,\d{2,3}){1,3})\s*(?:-|to|–)\s*(?:₹|INR|Rs\.?)?\s*(\d{1,3}(?:,\d{2,3}){1,3})',
    re.IGNORECASE
)
RE_LPA_PLAIN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|p\.?a\.?))',
    re.IGNORECASE
)
RE_LPA_SINGLE_PLAIN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|p\.?a\.?))',
    re.IGNORECASE
)

# ─── GBP/EUR Salary Regexes ───────────────────────────────────────────────────

RE_GBP_RANGE = re.compile(
    r'(?:£|GBP)\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\s*(?:-|to|–)\s*(?:£|GBP)?\s*(\d{2,3}(?:\.\d+)?)\s*[kK]',
    re.IGNORECASE
)
RE_EUR_RANGE = re.compile(
    r'(?:€|EUR)\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\s*(?:-|to|–)\s*(?:€|EUR)?\s*(\d{2,3}(?:\.\d+)?)\s*[kK]',
    re.IGNORECASE
)
RE_GBP_RANGE_FULL = re.compile(
    r'(?:£|GBP)\s*(\d{2,3},\d{3})\s*(?:-|to|–)\s*(?:£|GBP)?\s*(\d{2,3},\d{3})',
    re.IGNORECASE
)
RE_EUR_RANGE_FULL = re.compile(
    r'(?:€|EUR)\s*(\d{2,3},\d{3})\s*(?:-|to|–)\s*(?:€|EUR)?\s*(\d{2,3},\d{3})',
    re.IGNORECASE
)

# Negative lookahead patterns to prevent matching "401k", "100k users", "$5M funding"
RE_IGNORE_PATTERNS = re.compile(r'401\s*k|\b(?:users|downloads|requests|views|impressions|funding|series|raised)\b', re.IGNORECASE)

# ─── Multi-Domain Seniority Fallback Map ───────────────────────────────────────
# When job description doesn't explicitly mention YOE, infer from title keywords.
# Ordered by specificity: most specific titles first, broadest catch-all last.

SENIORITY_YOE_MAP = [
    # === Universal Seniority Prefixes (highest priority — apply to ANY domain) ===
    (('intern', 'internship', 'co-op', 'coop', 'apprentice', 'working student'), (0, 1)),
    (('junior', 'entry level', 'entry-level', 'associate', 'graduate', 'fresh', 'trainee', 'l1', 'level 1', 'level i', 'grade 1'), (0, 2)),
    (('staff', 'principal', 'distinguished', 'fellow', 'l6', 'l7'), (8, 12)),
    (('director', 'head of', 'vp', 'vice president', 'chief', 'cxo', 'cto', 'cfo', 'cmo', 'coo', 'cpo'), (10, 16)),

    # === HR / People ===
    (('hr business partner', 'hrbp'), (4, 7)),
    (('hr manager', 'hr director', 'people director'), (6, 10)),
    (('hr coordinator', 'hr assistant', 'people coordinator'), (0, 2)),
    (('talent acquisition lead', 'recruiting manager', 'recruitment manager'), (4, 7)),
    (('recruiter', 'talent acquisition', 'sourcer'), (1, 4)),
    (('people operations', 'people ops', 'hr generalist'), (2, 5)),
    (('compensation', 'total rewards', 'benefits manager'), (4, 7)),
    (('learning and development', 'l&d', 'training manager'), (3, 6)),

    # === Finance / Accounting ===
    (('cfo', 'chief financial officer'), (12, 18)),
    (('finance director', 'vp finance'), (8, 14)),
    (('finance manager', 'financial controller', 'controller'), (5, 8)),
    (('financial analyst', 'fp&a analyst', 'fp&a'), (2, 5)),
    (('senior accountant', 'accounting manager'), (4, 7)),
    (('accountant', 'bookkeeper', 'accounts payable', 'accounts receivable'), (1, 4)),
    (('chartered accountant', 'ca', 'cpa'), (2, 6)),
    (('tax analyst', 'tax manager', 'audit manager', 'internal audit'), (3, 6)),
    (('treasury', 'treasurer'), (4, 8)),
    (('investment analyst', 'portfolio analyst', 'credit analyst'), (2, 5)),

    # === Marketing ===
    (('cmo', 'chief marketing officer'), (12, 18)),
    (('marketing director', 'vp marketing', 'head of marketing'), (8, 12)),
    (('marketing manager', 'brand manager'), (4, 7)),
    (('marketing coordinator', 'marketing assistant', 'marketing associate'), (0, 2)),
    (('content strategist', 'content manager', 'content marketing'), (2, 5)),
    (('seo manager', 'seo specialist', 'sem specialist'), (2, 5)),
    (('growth marketing', 'growth manager', 'performance marketing'), (3, 6)),
    (('product marketing', 'pmm'), (3, 6)),
    (('social media manager', 'community manager'), (1, 4)),
    (('copywriter', 'content writer', 'technical writer'), (1, 4)),
    (('email marketing', 'lifecycle marketing', 'crm marketing'), (2, 5)),

    # === Sales ===
    (('sales director', 'vp sales', 'head of sales'), (8, 12)),
    (('sales manager', 'regional sales manager'), (4, 7)),
    (('account executive', 'ae'), (2, 5)),
    (('account manager', 'customer success manager', 'csm'), (2, 5)),
    (('account director', 'strategic account'), (5, 9)),
    (('business development representative', 'bdr'), (0, 2)),
    (('sales development representative', 'sdr'), (0, 2)),
    (('inside sales', 'outside sales'), (1, 4)),
    (('solutions engineer', 'sales engineer', 'pre-sales'), (3, 6)),
    (('revenue operations', 'revops', 'sales operations'), (2, 5)),

    # === Operations / Business ===
    (('coo', 'chief operating officer'), (12, 18)),
    (('operations director', 'head of operations'), (8, 12)),
    (('operations manager', 'business operations manager'), (4, 7)),
    (('operations analyst', 'operations associate'), (1, 3)),
    (('project manager', 'program manager'), (3, 6)),
    (('scrum master', 'agile coach'), (3, 6)),
    (('business analyst', 'business intelligence'), (2, 5)),
    (('management consultant', 'strategy consultant', 'consultant'), (2, 5)),
    (('supply chain', 'logistics', 'procurement'), (2, 6)),

    # === Data / Analytics ===
    (('data scientist', 'machine learning engineer', 'ml engineer', 'ai engineer'), (2, 5)),
    (('data analyst', 'analytics engineer', 'business intelligence analyst'), (1, 4)),
    (('data engineer', 'etl developer', 'data platform'), (2, 5)),
    (('research scientist', 'applied scientist', 'research engineer'), (3, 6)),

    # === Design ===
    (('design director', 'head of design', 'vp design'), (8, 12)),
    (('ux designer', 'ui designer', 'product designer', 'interaction designer'), (2, 5)),
    (('visual designer', 'graphic designer', 'brand designer'), (1, 4)),
    (('ux researcher', 'user researcher', 'design researcher'), (2, 5)),

    # === Legal ===
    (('general counsel', 'chief legal officer'), (10, 16)),
    (('legal counsel', 'corporate counsel', 'attorney'), (3, 7)),
    (('paralegal', 'legal assistant', 'legal coordinator'), (1, 3)),
    (('compliance manager', 'compliance officer', 'regulatory'), (3, 6)),
    (('privacy counsel', 'data privacy', 'dpo'), (3, 6)),

    # === Customer Support ===
    (('customer support manager', 'support director'), (4, 7)),
    (('customer support', 'customer service', 'support specialist', 'help desk'), (0, 3)),
    (('technical support', 'support engineer'), (1, 4)),

    # === Engineering (broad catch-all — lowest priority) ===
    (('lead', 'tech lead', 'team lead', 'engineering lead', 'architect'), (6, 10)),
    (('senior', 'sr.', 'sr ', 'l5', 'level 5', 'level iii'), (5, 8)),
    (('software engineer', 'developer', 'programmer', 'frontend', 'backend', 'fullstack',
      'devops', 'sre', 'platform engineer', 'infrastructure engineer',
      'security engineer', 'qa engineer', 'test engineer', 'mobile developer',
      'ios developer', 'android developer', 'web developer', 'cloud engineer'), (2, 5)),
]


def extract_yoe(description: Optional[str] = None, title: Optional[str] = None) -> Tuple[Optional[int], Optional[int], str]:
    """
    Deterministically extracts (min_yoe, max_yoe, confidence) from text.
    Confidence levels: 'high' (anchored requirement), 'medium' (general mention),
    'low' (title-based seniority fallback), or 'unknown' (none found).
    Zero LLM cost.
    """
    desc_str = description or ''
    title_str = title or ''
    
    # 0. Pre-clean text to neutralize company-centric experience phrasing
    # e.g., "Our company has 15 years of experience in the industry"
    cleaned_desc = RE_YOE_NEGATIVE.sub(' [company_history] ', desc_str)
    search_text = f"{title_str} {cleaned_desc}".lower()

    # 1. High-Confidence: Requirement-anchored Range: "requires 3-5 years", "minimum 2 to 4 yrs"
    match = RE_YOE_REQ_RANGE.search(search_text)
    if match:
        val1, val2 = int(match.group(1)), int(match.group(2))
        if val1 <= 15 and val2 <= 20 and val1 <= val2:
            return val1, val2, "high"

    # 2. High-Confidence: Requirement-anchored Plus: "requires 3+ years experience"
    match = RE_YOE_REQ_PLUS.search(search_text)
    if match:
        val = int(match.group(1))
        if val <= 15:
            return val, val + 3, "high"

    # 3. High-Confidence: Explicit Minimum: "minimum 4 years"
    match = RE_YOE_REQ_MIN.search(search_text)
    if match:
        val = int(match.group(1))
        if val <= 15:
            return val, val + 3, "high"

    # 4. Medium-Confidence: General Range without requirement verbs
    match = RE_YOE_RANGE.search(search_text)
    if match:
        val1, val2 = int(match.group(1)), int(match.group(2))
        if val1 <= 15 and val2 <= 20 and val1 <= val2:
            return val1, val2, "medium"

    # 5. Medium-Confidence: General Plus: "3+ years of experience"
    match = RE_YOE_PLUS.search(search_text)
    if match:
        val = int(match.group(1))
        if val <= 15:
            return val, val + 3, "medium"

    # 6. Medium-Confidence: General: "5 years experience"
    match = RE_YOE_GENERAL.search(search_text)
    if match:
        val = int(match.group(1))
        if val <= 15:
            return val, val + 2, "medium"

    # 7. Low-Confidence: Fallback infer from Job Title Seniority
    if title:
        title_lower = title.lower()
        for keywords, yoe_range in SENIORITY_YOE_MAP:
            if any(kw in title_lower for kw in keywords):
                return yoe_range[0], yoe_range[1], "low"

    return None, None, "unknown"


def extract_salary(description: Optional[str] = None, title: Optional[str] = None,
                   location_currency: Optional[str] = None) -> Tuple[Optional[float], Optional[float], str]:
    """
    Deterministically extracts (min_salary, max_salary, currency) from job text.
    Supports USD, INR (lakh/LPA), GBP, EUR formats.
    Zero LLM cost.
    """
    text = f"{title or ''} {description or ''}"
    text_lower = text.lower()

    # Detect currency from text content
    currency = "USD"
    if "₹" in text or "inr" in text_lower or "lpa" in text_lower or "lakhs" in text_lower or "lakh" in text_lower:
        currency = "INR"
    elif "gbp" in text_lower or "£" in text:
        currency = "GBP"
    elif "eur" in text_lower or "€" in text:
        currency = "EUR"
    elif "cad" in text_lower or "c$" in text:
        currency = "CAD"
    elif "aud" in text_lower or "a$" in text:
        currency = "AUD"
    elif "sgd" in text_lower or "s$" in text:
        currency = "SGD"

    # ── INR: LPA / Lakh notation ──
    if currency == "INR" or location_currency == "INR":
        # Range LPA: "₹15 - ₹25 lpa", "INR 10-20 lakhs per annum"
        match = RE_INR_LPA_RANGE.search(text)
        if match:
            min_lpa, max_lpa = float(match.group(1)), float(match.group(2))
            if 1 <= min_lpa <= 200 and 1 <= max_lpa <= 500 and min_lpa <= max_lpa:
                return min_lpa * 100_000, max_lpa * 100_000, "INR"

        # Plain LPA range: "10-20 lpa"
        match = RE_LPA_PLAIN.search(text)
        if match:
            min_lpa, max_lpa = float(match.group(1)), float(match.group(2))
            if 1 <= min_lpa <= 200 and 1 <= max_lpa <= 500 and min_lpa <= max_lpa:
                return min_lpa * 100_000, max_lpa * 100_000, "INR"

        # Single LPA: "₹15 lpa"
        match = RE_INR_LPA_SINGLE.search(text)
        if match:
            val = float(match.group(1))
            if 1 <= val <= 200:
                return val * 100_000, val * 100_000, "INR"

        # Single plain LPA: "15 lpa"
        match = RE_LPA_SINGLE_PLAIN.search(text)
        if match:
            val = float(match.group(1))
            if 1 <= val <= 200:
                return val * 100_000, val * 100_000, "INR"

        # Full INR range: "₹15,00,000 - ₹25,00,000"
        match = RE_INR_RANGE_FULL.search(text)
        if match:
            min_str = match.group(1).replace(',', '')
            max_str = match.group(2).replace(',', '')
            min_val, max_val = float(min_str), float(max_str)
            if 100_000 <= min_val <= 50_000_000 and 100_000 <= max_val <= 100_000_000:
                return min_val, max_val, "INR"

    # ── GBP ──
    if currency == "GBP" or location_currency == "GBP":
        match = RE_GBP_RANGE.search(text)
        if match:
            min_k, max_k = float(match.group(1)), float(match.group(2))
            if 15 <= min_k <= 500 and 15 <= max_k <= 800 and min_k <= max_k:
                return min_k * 1000.0, max_k * 1000.0, "GBP"
        match = RE_GBP_RANGE_FULL.search(text)
        if match:
            min_str = match.group(1).replace(',', '')
            max_str = match.group(2).replace(',', '')
            min_val, max_val = float(min_str), float(max_str)
            if 15000 <= min_val <= 500000 and 15000 <= max_val <= 800000:
                return min_val, max_val, "GBP"

    # ── EUR ──
    if currency == "EUR" or location_currency == "EUR":
        match = RE_EUR_RANGE.search(text)
        if match:
            min_k, max_k = float(match.group(1)), float(match.group(2))
            if 15 <= min_k <= 500 and 15 <= max_k <= 800 and min_k <= max_k:
                return min_k * 1000.0, max_k * 1000.0, "EUR"
        match = RE_EUR_RANGE_FULL.search(text)
        if match:
            min_str = match.group(1).replace(',', '')
            max_str = match.group(2).replace(',', '')
            min_val, max_val = float(min_str), float(max_str)
            if 15000 <= min_val <= 500000 and 15000 <= max_val <= 800000:
                return min_val, max_val, "EUR"

    # ── USD (default / catch-all) ──

    # 1. Hourly Range: e.g. "$50 - $75 / hr" -> Annualized (x 2080)
    match = RE_HOURLY_RANGE.search(text)
    if match:
        h_min, h_max = float(match.group(1)), float(match.group(2))
        if 15 <= h_min <= 500 and 15 <= h_max <= 500 and h_min <= h_max:
            return round(h_min * 2080, 2), round(h_max * 2080, 2), currency

    # 2. Hourly Single: e.g. "$65/hr"
    match = RE_HOURLY_SINGLE.search(text)
    if match:
        h_val = float(match.group(1))
        if 15 <= h_val <= 500:
            ann_val = round(h_val * 2080, 2)
            return ann_val, ann_val, currency

    # 3. Range with K: "$120k - $160k"
    match = RE_SALARY_RANGE_K.search(text)
    if match:
        min_k, max_k = float(match.group(1)), float(match.group(2))
        if 20 <= min_k <= 800 and 20 <= max_k <= 1000 and min_k <= max_k:
            return min_k * 1000.0, max_k * 1000.0, currency

    # 4. Range Full Numbers: "$120,000 - $160,000"
    match = RE_SALARY_RANGE_FULL.search(text)
    if match:
        min_str = match.group(1).replace(',', '')
        max_str = match.group(2).replace(',', '')
        min_val, max_val = float(min_str), float(max_str)
        if 20000 <= min_val <= 800000 and 20000 <= max_val <= 1000000 and min_val <= max_val:
            return min_val, max_val, currency

    # 5. Single Full: "$150,000 / year"
    match = RE_SALARY_SINGLE_FULL.search(text)
    if match:
        val_str = match.group(1).replace(',', '')
        val = float(val_str)
        if 20000 <= val <= 800000:
            return val, val, currency

    # 6. Single K: "$140k/yr"
    match = RE_SALARY_SINGLE_K.search(text)
    if match:
        # Check that it's not a 401k reference
        start_idx = max(0, match.start() - 10)
        prefix = text[start_idx:match.start()].lower()
        if '401' not in prefix:
            val_k = float(match.group(1))
            if 30 <= val_k <= 600:
                return val_k * 1000.0, val_k * 1000.0, currency

    # If no salary found in text but we know the location currency, return that currency
    final_currency = currency if currency != "USD" else (location_currency or currency)
    return None, None, final_currency


RE_INTERN = re.compile(r'\b(?:internships?|interns?|co-?ops?|apprentices?(?:hip)?)(?:\s|$)', re.IGNORECASE)
RE_CONTRACT = re.compile(r'\b(?:contracts?|contractors?|c2c|w2\s*contract|freelancers?|temporary|temps?)\b', re.IGNORECASE)
RE_PART_TIME = re.compile(r'\b(?:part[\s-]time|paid\s+hourly|hourly\s+(?:rate|basis|wage)|\d+\s*(?:hours|hrs)\s*(?:\/|per)\s*week)\b', re.IGNORECASE)

RE_STRUCTURED_TYPE = re.compile(
    r'(?:employment|job|position|work)\s*type\s*[:\-]\s*([a-zA-Z\s\-]+)',
    re.IGNORECASE
)

def extract_employment_type(description: Optional[str] = None, title: Optional[str] = None, raw_type: Optional[str] = None) -> str:
    """
    Normalizes employment type to: 'full-time', 'part-time', 'contract', or 'internship'.
    Prioritizes structured attributes and job titles. Avoids false positives from phrases
    like 'excluding internships' or 'internal operations'.
    """
    if raw_type:
        raw_lower = raw_type.lower()
        if RE_INTERN.search(raw_lower):
            return 'internship'
        if RE_CONTRACT.search(raw_lower):
            return 'contract'
        if RE_PART_TIME.search(raw_lower):
            return 'part-time'
        if 'full' in raw_lower:
            return 'full-time'

    # Check title first (highest precision for real role identity)
    if title:
        title_lower = title.lower()
        if RE_INTERN.search(title_lower):
            return 'internship'
        if RE_CONTRACT.search(title_lower):
            return 'contract'
        if RE_PART_TIME.search(title_lower):
            return 'part-time'

    # Check for explicit structured lines in description: e.g. "Job Type: Contract", "Employment Type: Internship"
    if description:
        m = RE_STRUCTURED_TYPE.search(description)
        if m:
            val = m.group(1).lower()
            if RE_INTERN.search(val):
                return 'internship'
            if RE_CONTRACT.search(val):
                return 'contract'
            if RE_PART_TIME.search(val):
                return 'part-time'
            if 'full' in val:
                return 'full-time'

    # Check description for explicit part-time indicators
    if description and RE_PART_TIME.search(description):
        return 'part-time'

    # Default for engineering and professional roles is full-time
    return 'full-time'


def enrich_job_data(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes a raw or partially populated job dictionary and adds normalized
    yoe, yoe_min, yoe_max, min_salary, max_salary, currency, employment_type,
    country_code.
    """
    enriched = dict(job_data)
    title = enriched.get('title', '')
    desc = enriched.get('description') or enriched.get('full_description') or ''
    location = enriched.get('location') or ''

    # 0. Normalize location → country_code + currency
    loc_info = normalize_location(location)
    enriched['country_code'] = loc_info['country_code']
    location_currency = loc_info.get('currency')

    # 1. Extract YOE
    existing_yoe = enriched.get('yoe')
    yoe_min, yoe_max, yoe_conf = extract_yoe(desc, title)
    enriched['yoe_min'] = yoe_min if enriched.get('yoe_min') is None else enriched.get('yoe_min')
    enriched['yoe_max'] = yoe_max if enriched.get('yoe_max') is None else enriched.get('yoe_max')
    enriched['yoe_confidence'] = enriched.get('yoe_confidence') or yoe_conf
    if existing_yoe is None:
        enriched['yoe'] = enriched['yoe_min']

    # 1.5 Extract Grounded Tech Stack (Zero Hallucination)
    if enriched.get('tech_stack') is None:
        enriched['tech_stack'] = extract_deterministic_tech_stack(f"{title} {desc}")

    # 2. Extract Salary (now with location-aware currency detection)
    existing_min = enriched.get('min_salary')
    existing_max = enriched.get('max_salary')
    if existing_min is None and existing_max is None:
        s_min, s_max, s_curr = extract_salary(desc, title, location_currency)
        enriched['min_salary'] = s_min
        enriched['max_salary'] = s_max
        enriched['currency'] = s_curr
    else:
        # If salary exists but currency is wrong (defaulted to USD for India jobs), fix it
        if enriched.get('currency', 'USD') == 'USD' and location_currency and location_currency != 'USD':
            # Only override if salary values look like they're in the local currency
            # (e.g., 1500000 is clearly INR not USD)
            if existing_min and existing_min > 500_000 and location_currency == 'INR':
                enriched['currency'] = 'INR'
            elif existing_max and existing_max > 500_000 and location_currency == 'INR':
                enriched['currency'] = 'INR'

    # If no currency detected from text, use location-based currency
    if enriched.get('currency', 'USD') == 'USD' and location_currency and location_currency != 'USD':
        enriched['currency'] = location_currency

    # 3. Extract Employment Type
    enriched['employment_type'] = extract_employment_type(
        desc, title, enriched.get('raw_employment_type')
    )

    return enriched
