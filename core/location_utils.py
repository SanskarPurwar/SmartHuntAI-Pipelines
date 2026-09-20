"""
Zero-cost location intelligence module for SmartHunt AI.
Maps raw location strings → structured country/currency data without any external API calls.
"""
import re
from typing import Dict, Optional, Tuple

# ─── City → Country Code Mapping (~200 common cities) ─────────────────────────

CITY_TO_COUNTRY: Dict[str, str] = {
    # India
    'bengaluru': 'IN', 'bangalore': 'IN', 'mumbai': 'IN', 'delhi': 'IN',
    'new delhi': 'IN', 'hyderabad': 'IN', 'pune': 'IN', 'gurugram': 'IN',
    'gurgaon': 'IN', 'chennai': 'IN', 'noida': 'IN', 'kolkata': 'IN',
    'ahmedabad': 'IN', 'jaipur': 'IN', 'kochi': 'IN', 'thiruvananthapuram': 'IN',
    'indore': 'IN', 'chandigarh': 'IN', 'lucknow': 'IN', 'coimbatore': 'IN',
    'nagpur': 'IN', 'mysore': 'IN', 'visakhapatnam': 'IN', 'bhubaneswar': 'IN',

    # USA
    'san francisco': 'US', 'new york': 'US', 'los angeles': 'US', 'chicago': 'US',
    'seattle': 'US', 'austin': 'US', 'boston': 'US', 'denver': 'US',
    'atlanta': 'US', 'miami': 'US', 'dallas': 'US', 'houston': 'US',
    'portland': 'US', 'san diego': 'US', 'san jose': 'US', 'phoenix': 'US',
    'philadelphia': 'US', 'minneapolis': 'US', 'salt lake city': 'US',
    'nashville': 'US', 'raleigh': 'US', 'charlotte': 'US', 'pittsburgh': 'US',
    'detroit': 'US', 'washington': 'US', 'washington, d.c.': 'US', 'dc': 'US',
    'palo alto': 'US', 'menlo park': 'US', 'mountain view': 'US', 'cupertino': 'US',
    'sunnyvale': 'US', 'redwood city': 'US', 'santa clara': 'US', 'irvine': 'US',
    'bellevue': 'US', 'kirkland': 'US', 'redmond': 'US', 'tampa': 'US',
    'orlando': 'US', 'sacramento': 'US', 'st. louis': 'US', 'columbus': 'US',
    'indianapolis': 'US', 'kansas city': 'US', 'milwaukee': 'US',

    # UK
    'london': 'GB', 'manchester': 'GB', 'birmingham': 'GB', 'edinburgh': 'GB',
    'glasgow': 'GB', 'bristol': 'GB', 'leeds': 'GB', 'liverpool': 'GB',
    'cambridge': 'GB', 'oxford': 'GB', 'belfast': 'GB', 'cardiff': 'GB',
    'reading': 'GB', 'bath': 'GB', 'brighton': 'GB', 'sheffield': 'GB',

    # Canada (cities and provinces)
    'toronto': 'CA', 'vancouver': 'CA', 'montreal': 'CA', 'ottawa': 'CA',
    'calgary': 'CA', 'edmonton': 'CA', 'winnipeg': 'CA', 'quebec': 'CA',
    'waterloo': 'CA', 'kitchener': 'CA', 'halifax': 'CA', 'victoria': 'CA',
    'ontario': 'CA', 'british columbia': 'CA', 'alberta': 'CA',
    'manitoba': 'CA', 'saskatchewan': 'CA', 'nova scotia': 'CA',

    # Germany
    'berlin': 'DE', 'munich': 'DE', 'hamburg': 'DE', 'frankfurt': 'DE',
    'cologne': 'DE', 'stuttgart': 'DE', 'düsseldorf': 'DE', 'dusseldorf': 'DE',
    'dresden': 'DE', 'leipzig': 'DE', 'nuremberg': 'DE',

    # France
    'paris': 'FR', 'lyon': 'FR', 'marseille': 'FR', 'toulouse': 'FR',
    'nice': 'FR', 'bordeaux': 'FR', 'nantes': 'FR', 'lille': 'FR',

    # Netherlands
    'amsterdam': 'NL', 'rotterdam': 'NL', 'the hague': 'NL', 'utrecht': 'NL',
    'eindhoven': 'NL',

    # Ireland
    'dublin': 'IE', 'cork': 'IE', 'galway': 'IE', 'limerick': 'IE',

    # Australia
    'sydney': 'AU', 'melbourne': 'AU', 'brisbane': 'AU', 'perth': 'AU',
    'adelaide': 'AU', 'canberra': 'AU',

    # Singapore
    'singapore': 'SG',

    # Japan
    'tokyo': 'JP', 'osaka': 'JP', 'kyoto': 'JP', 'yokohama': 'JP',
    'nagoya': 'JP', 'fukuoka': 'JP',

    # South Korea
    'seoul': 'KR', 'busan': 'KR',

    # Israel
    'tel aviv': 'IL', 'jerusalem': 'IL', 'haifa': 'IL',

    # UAE
    'dubai': 'AE', 'abu dhabi': 'AE',

    # Brazil
    'são paulo': 'BR', 'sao paulo': 'BR', 'rio de janeiro': 'BR',

    # Spain
    'madrid': 'ES', 'barcelona': 'ES', 'valencia': 'ES', 'seville': 'ES',

    # Italy
    'milan': 'IT', 'rome': 'IT', 'turin': 'IT', 'florence': 'IT',

    # Sweden
    'stockholm': 'SE', 'gothenburg': 'SE', 'malmö': 'SE',

    # Denmark
    'copenhagen': 'DK',

    # Norway
    'oslo': 'NO',

    # Finland
    'helsinki': 'FI',

    # Switzerland
    'zurich': 'CH', 'geneva': 'CH', 'basel': 'CH', 'bern': 'CH',

    # Poland
    'warsaw': 'PL', 'krakow': 'PL', 'wroclaw': 'PL', 'gdansk': 'PL',

    # Czech Republic
    'prague': 'CZ', 'brno': 'CZ',

    # Portugal
    'lisbon': 'PT', 'porto': 'PT',

    # Argentina
    'buenos aires': 'AR',

    # Mexico
    'mexico city': 'MX', 'guadalajara': 'MX', 'monterrey': 'MX',

    # China
    'beijing': 'CN', 'shanghai': 'CN', 'shenzhen': 'CN', 'hangzhou': 'CN',
    'guangzhou': 'CN', 'chengdu': 'CN',

    # Hong Kong
    'hong kong': 'HK',

    # Taiwan
    'taipei': 'TW',

    # Philippines
    'manila': 'PH', 'makati': 'PH', 'cebu': 'PH',

    # Vietnam
    'ho chi minh': 'VN', 'hanoi': 'VN',

    # Thailand
    'bangkok': 'TH',

    # Indonesia
    'jakarta': 'ID',

    # Malaysia
    'kuala lumpur': 'MY',

    # New Zealand
    'auckland': 'NZ', 'wellington': 'NZ',

    # Romania
    'bucharest': 'RO', 'cluj': 'RO',

    # South Africa
    'cape town': 'ZA', 'johannesburg': 'ZA',

    # Kenya
    'nairobi': 'KE',

    # Nigeria
    'lagos': 'NG',

    # Egypt
    'cairo': 'EG',

    # Colombia
    'bogota': 'CO', 'medellin': 'CO',

    # Chile
    'santiago': 'CL',

    # Peru
    'lima': 'PE',
}

# Country name → country code (for "United States", "India", etc. in location strings)
COUNTRY_NAME_TO_CODE: Dict[str, str] = {
    'united states': 'US', 'usa': 'US', 'us': 'US', 'america': 'US',
    'india': 'IN', 'bharat': 'IN',
    'united kingdom': 'GB', 'uk': 'GB', 'england': 'GB', 'great britain': 'GB', 'scotland': 'GB', 'wales': 'GB',
    'canada': 'CA',
    'germany': 'DE', 'deutschland': 'DE',
    'france': 'FR',
    'netherlands': 'NL', 'holland': 'NL',
    'ireland': 'IE',
    'australia': 'AU',
    'singapore': 'SG',
    'japan': 'JP',
    'south korea': 'KR', 'korea': 'KR',
    'israel': 'IL',
    'uae': 'AE', 'united arab emirates': 'AE',
    'brazil': 'BR',
    'spain': 'ES',
    'italy': 'IT',
    'sweden': 'SE',
    'denmark': 'DK',
    'norway': 'NO',
    'finland': 'FI',
    'switzerland': 'CH',
    'poland': 'PL',
    'czech republic': 'CZ', 'czechia': 'CZ',
    'portugal': 'PT',
    'argentina': 'AR',
    'mexico': 'MX',
    'china': 'CN',
    'hong kong': 'HK',
    'taiwan': 'TW',
    'philippines': 'PH',
    'vietnam': 'VN',
    'thailand': 'TH',
    'indonesia': 'ID',
    'malaysia': 'MY',
    'new zealand': 'NZ',
    'romania': 'RO',
    'south africa': 'ZA',
    'kenya': 'KE',
    'nigeria': 'NG',
    'egypt': 'EG',
    'colombia': 'CO',
    'chile': 'CL',
    'peru': 'PE',
    'austria': 'AT',
    'belgium': 'BE',
    'turkey': 'TR', 'türkiye': 'TR',
    'russia': 'RU',
    'ukraine': 'UA',
    'greece': 'GR',
    'hungary': 'HU',
    'croatia': 'HR',
    'serbia': 'RS',
    'bulgaria': 'BG',
    'estonia': 'EE',
    'latvia': 'LV',
    'lithuania': 'LT',
    'luxembourg': 'LU',
    'qatar': 'QA',
    'saudi arabia': 'SA',
    'bahrain': 'BH',
    'oman': 'OM',
    'kuwait': 'KW',
    'pakistan': 'PK',
    'bangladesh': 'BD',
    'sri lanka': 'LK',
    'nepal': 'NP',
}

# US State abbreviations → US country code
US_STATES: Dict[str, str] = {
    'al': 'US', 'ak': 'US', 'az': 'US', 'ar': 'US', 'ca': 'US', 'co': 'US',
    'ct': 'US', 'de': 'US', 'fl': 'US', 'ga': 'US', 'hi': 'US', 'id': 'US',
    'il': 'US', 'in': 'US', 'ia': 'US', 'ks': 'US', 'ky': 'US', 'la': 'US',
    'me': 'US', 'md': 'US', 'ma': 'US', 'mi': 'US', 'mn': 'US', 'ms': 'US',
    'mo': 'US', 'mt': 'US', 'ne': 'US', 'nv': 'US', 'nh': 'US', 'nj': 'US',
    'nm': 'US', 'ny': 'US', 'nc': 'US', 'nd': 'US', 'oh': 'US', 'ok': 'US',
    'or': 'US', 'pa': 'US', 'ri': 'US', 'sc': 'US', 'sd': 'US', 'tn': 'US',
    'tx': 'US', 'ut': 'US', 'vt': 'US', 'va': 'US', 'wa': 'US', 'wv': 'US',
    'wi': 'US', 'wy': 'US', 'dc': 'US',
}

# Indian State names → IN
INDIAN_STATES = {
    'karnataka', 'maharashtra', 'tamil nadu', 'telangana', 'kerala',
    'andhra pradesh', 'west bengal', 'rajasthan', 'gujarat', 'uttar pradesh',
    'madhya pradesh', 'haryana', 'punjab', 'odisha', 'bihar', 'jharkhand',
    'chhattisgarh', 'uttarakhand', 'himachal pradesh', 'goa', 'assam',
    'jammu and kashmir', 'delhi ncr',
}

# ─── Country Code → Currency Code ──────────────────────────────────────────────

COUNTRY_TO_CURRENCY: Dict[str, str] = {
    'US': 'USD', 'IN': 'INR', 'GB': 'GBP', 'CA': 'CAD', 'AU': 'AUD',
    'DE': 'EUR', 'FR': 'EUR', 'NL': 'EUR', 'IE': 'EUR', 'ES': 'EUR',
    'IT': 'EUR', 'PT': 'EUR', 'AT': 'EUR', 'BE': 'EUR', 'FI': 'EUR',
    'GR': 'EUR', 'LU': 'EUR', 'EE': 'EUR', 'LV': 'EUR', 'LT': 'EUR',
    'HR': 'EUR',
    'SG': 'SGD', 'JP': 'JPY', 'KR': 'KRW', 'CN': 'CNY', 'HK': 'HKD',
    'TW': 'TWD', 'IL': 'ILS', 'AE': 'AED', 'BR': 'BRL', 'MX': 'MXN',
    'SE': 'SEK', 'DK': 'DKK', 'NO': 'NOK', 'CH': 'CHF', 'PL': 'PLN',
    'CZ': 'CZK', 'RO': 'RON', 'HU': 'HUF', 'BG': 'BGN', 'RS': 'RSD',
    'TR': 'TRY', 'RU': 'RUB', 'UA': 'UAH', 'ZA': 'ZAR', 'KE': 'KES',
    'NG': 'NGN', 'EG': 'EGP', 'PH': 'PHP', 'VN': 'VND', 'TH': 'THB',
    'ID': 'IDR', 'MY': 'MYR', 'NZ': 'NZD', 'AR': 'ARS', 'CO': 'COP',
    'CL': 'CLP', 'PE': 'PEN', 'QA': 'QAR', 'SA': 'SAR', 'BH': 'BHD',
    'OM': 'OMR', 'KW': 'KWD', 'PK': 'PKR', 'BD': 'BDT', 'LK': 'LKR',
    'NP': 'NPR',
}

# ─── Currency Display ──────────────────────────────────────────────────────────

CURRENCY_SYMBOLS: Dict[str, str] = {
    'USD': '$', 'INR': '₹', 'GBP': '£', 'EUR': '€', 'CAD': 'C$', 'AUD': 'A$',
    'SGD': 'S$', 'JPY': '¥', 'CNY': '¥', 'KRW': '₩', 'CHF': 'CHF ',
    'SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr', 'PLN': 'zł', 'CZK': 'Kč',
    'HKD': 'HK$', 'TWD': 'NT$', 'ILS': '₪', 'AED': 'AED ', 'BRL': 'R$',
    'MXN': 'MX$', 'ZAR': 'R', 'TRY': '₺', 'THB': '฿', 'MYR': 'RM',
    'PHP': '₱', 'PKR': 'Rs', 'BDT': '৳', 'LKR': 'Rs', 'NPR': 'Rs',
    'NZD': 'NZ$',
}

# Regex to detect US state abbreviations like ", CA", ", NY" in location strings
RE_US_STATE = re.compile(r',\s*([A-Z]{2})\s*$')
RE_US_STATE_FULL = re.compile(r'\b(california|texas|new york|florida|illinois|ohio|georgia|'
                              r'virginia|massachusetts|washington|colorado|oregon|'
                              r'north carolina|pennsylvania|maryland|minnesota|'
                              r'connecticut|arizona|tennessee|utah|nevada|michigan|'
                              r'indiana|missouri|wisconsin|alabama|kentucky|south carolina|'
                              r'louisiana|oklahoma|iowa|mississippi|arkansas|kansas|'
                              r'nebraska|new mexico|idaho|hawaii|montana|wyoming|'
                              r'west virginia|maine|new hampshire|vermont|'
                              r'rhode island|delaware|south dakota|north dakota|'
                              r'district of columbia)\b', re.IGNORECASE)

# Location groupings for frontend filter dropdown
LOCATION_GROUPS: Dict[str, list] = {
    'India': ['bengaluru', 'mumbai', 'delhi', 'hyderabad', 'pune', 'gurugram',
              'gurgaon', 'chennai', 'noida', 'kolkata', 'india', 'karnataka',
              'maharashtra', 'tamil nadu', 'telangana'],
    'USA': ['san francisco', 'new york', 'los angeles', 'chicago', 'seattle',
            'austin', 'boston', 'denver', 'atlanta', 'united states', 'usa'],
    'UK': ['london', 'manchester', 'birmingham', 'edinburgh', 'united kingdom'],
    'Europe': ['berlin', 'paris', 'amsterdam', 'dublin', 'stockholm', 'madrid',
               'barcelona', 'munich', 'zurich', 'copenhagen', 'lisbon', 'prague',
               'warsaw', 'milan'],
    'Canada': ['toronto', 'vancouver', 'montreal', 'ottawa', 'canada'],
    'Singapore': ['singapore'],
    'Japan': ['tokyo', 'osaka', 'japan'],
    'Australia': ['sydney', 'melbourne', 'brisbane', 'australia'],
    'Remote': ['remote'],
}


def normalize_location(raw_location: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Parses a raw location string into structured location data.
    Returns: { city, country, country_code, currency, is_remote }
    
    Examples:
        "San Francisco, CA" → { country_code: "US", currency: "USD", is_remote: False }
        "Bengaluru, Karnataka, India" → { country_code: "IN", currency: "INR", is_remote: False }
        "US - Remote" → { country_code: "US", currency: "USD", is_remote: True }
        "Remote" → { country_code: None, currency: None, is_remote: True }
    """
    result = {
        'city': None,
        'country': None,
        'country_code': None,
        'currency': None,
        'is_remote': False,
    }

    if not raw_location or not raw_location.strip():
        return result

    loc_lower = raw_location.strip().lower()
    loc_clean = raw_location.strip()

    # 1. Check for remote
    if 'remote' in loc_lower:
        result['is_remote'] = True

    # 2. Try to find country code from country names in the string
    for country_name, code in sorted(COUNTRY_NAME_TO_CODE.items(), key=lambda x: -len(x[0])):
        # Use word boundary matching for short names, substring for longer ones
        if len(country_name) <= 3:
            if re.search(r'\b' + re.escape(country_name) + r'\b', loc_lower):
                result['country_code'] = code
                result['country'] = country_name.title()
                break
        else:
            if country_name in loc_lower:
                result['country_code'] = code
                result['country'] = country_name.title()
                break

    # 3. Try US state abbreviation (e.g., ", CA", ", NY")
    if not result['country_code']:
        m = RE_US_STATE.search(loc_clean)
        if m:
            state_abbr = m.group(1).lower()
            if state_abbr in US_STATES:
                result['country_code'] = 'US'
                result['country'] = 'United States'

    # 4. Try US state full name
    if not result['country_code']:
        if RE_US_STATE_FULL.search(loc_lower):
            result['country_code'] = 'US'
            result['country'] = 'United States'

    # 5. Try Indian state names
    if not result['country_code']:
        for state in INDIAN_STATES:
            if state in loc_lower:
                result['country_code'] = 'IN'
                result['country'] = 'India'
                break

    # 6. Try city names (longest match first to avoid false positives)
    if not result['country_code']:
        for city, code in sorted(CITY_TO_COUNTRY.items(), key=lambda x: -len(x[0])):
            if city in loc_lower:
                result['country_code'] = code
                result['city'] = city.title()
                break

    # 7. Derive currency from country code
    if result['country_code']:
        result['currency'] = COUNTRY_TO_CURRENCY.get(result['country_code'], 'USD')

    return result


def get_currency_symbol(currency_code: Optional[str]) -> str:
    """Returns the display symbol for a currency code. Defaults to '$'."""
    if not currency_code:
        return '$'
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code + ' ')


def format_salary_display(amount: Optional[float], currency: Optional[str] = 'USD') -> str:
    """
    Formats a salary amount with the appropriate currency symbol and scale.
    Examples:
        (120000, 'USD') → "$120k"
        (1500000, 'INR') → "₹15L"
        (80000, 'GBP') → "£80k"
        (15000000, 'JPY') → "¥15M"
    """
    if amount is None:
        return ''

    symbol = get_currency_symbol(currency)
    curr = (currency or 'USD').upper()

    # INR: Use Lakhs (L) notation
    if curr == 'INR':
        if amount >= 10_000_000:
            return f"{symbol}{amount / 10_000_000:.1f}Cr"
        elif amount >= 100_000:
            return f"{symbol}{amount / 100_000:.1f}L"
        elif amount >= 1_000:
            return f"{symbol}{amount / 1_000:.0f}k"
        else:
            return f"{symbol}{amount:.0f}"

    # JPY, KRW: Use M notation (millions)
    if curr in ('JPY', 'KRW', 'VND', 'IDR'):
        if amount >= 1_000_000:
            return f"{symbol}{amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"{symbol}{amount / 1_000:.0f}k"
        else:
            return f"{symbol}{amount:.0f}"

    # Default (USD, GBP, EUR, CAD, AUD, SGD, etc.): Use k notation
    if amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{symbol}{amount / 1_000:.0f}k"
    else:
        return f"{symbol}{amount:.0f}"


def format_salary_range(min_salary: Optional[float], max_salary: Optional[float],
                        currency: Optional[str] = 'USD') -> str:
    """
    Formats a salary range for display.
    Examples:
        (120000, 160000, 'USD') → "$120k - $160k"
        (1500000, 2500000, 'INR') → "₹15L - ₹25L"
    """
    if min_salary and max_salary:
        return f"{format_salary_display(min_salary, currency)} - {format_salary_display(max_salary, currency)}"
    elif min_salary:
        return f"{format_salary_display(min_salary, currency)}+"
    elif max_salary:
        return f"Up to {format_salary_display(max_salary, currency)}"
    return ''


def get_location_filter_sql(location_group: str) -> Tuple[str, list]:
    """
    Returns a SQL WHERE clause fragment and params for filtering by location group.
    The group name maps to LOCATION_GROUPS keys or a free-text city.
    """
    if not location_group or location_group == 'all':
        return '', []

    if location_group.lower() == 'remote':
        return " AND (gj.location ILIKE %s OR gj.title ILIKE %s)", ['%remote%', '%remote%']

    # Check if it's a known group
    keywords = LOCATION_GROUPS.get(location_group)
    if keywords:
        conditions = ' OR '.join(['gj.location ILIKE %s' for _ in keywords])
        params = [f'%{kw}%' for kw in keywords]
        return f" AND ({conditions})", params

    # Free-text location search
    return " AND gj.location ILIKE %s", [f'%{location_group}%']


if __name__ == '__main__':
    # Self-test
    tests = [
        ("San Francisco, CA", "US", "USD"),
        ("Bengaluru, Karnataka, India", "IN", "INR"),
        ("London, United Kingdom", "GB", "GBP"),
        ("US - Remote", "US", "USD"),
        ("Remote", None, None),
        ("New York, NY (HQ)", "US", "USD"),
        ("Dublin, Ireland", "IE", "EUR"),
        ("Singapore", "SG", "SGD"),
        ("Tokyo, Japan", "JP", "JPY"),
        ("Poland - Remote OR Romania - Remote", "RO", "RON"),  # last country wins in multi-country strings
        ("San Francisco, CA • New York, NY • United States", "US", "USD"),
        ("Ontario - Remote", "CA", "CAD"),
        ("Washington, D.C.", "US", "USD"),
    ]
    
    for loc, expected_cc, expected_curr in tests:
        result = normalize_location(loc)
        status = "✅" if result['country_code'] == expected_cc and result['currency'] == expected_curr else "❌"
        print(f"{status} '{loc}' → cc={result['country_code']} curr={result['currency']} (expected cc={expected_cc} curr={expected_curr})")

    # Salary display tests
    assert format_salary_display(120000, 'USD') == "$120k"
    assert format_salary_display(1500000, 'INR') == "₹15.0L"
    assert format_salary_display(80000, 'GBP') == "£80k"
    print("\n✅ All location_utils tests passed.")
