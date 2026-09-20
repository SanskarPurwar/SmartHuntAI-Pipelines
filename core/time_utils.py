import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union

def parse_posted_at(raw_val: Optional[Union[str, int, float, datetime]], reference_dt: Optional[datetime] = None) -> datetime:
    """
    Universal normalizer for job posting dates and timestamps.
    Parses relative expressions ('30 minutes ago', '2 hours ago', 'yesterday', 'just now'),
    epoch timestamps (milliseconds or seconds), ISO 8601 strings, and date formats.
    Always returns a timezone-aware UTC datetime.
    """
    now = reference_dt or datetime.now(timezone.utc)
    if not now.tzinfo:
        now = now.replace(tzinfo=timezone.utc)

    if raw_val is None:
        return now

    if isinstance(raw_val, datetime):
        return raw_val if raw_val.tzinfo else raw_val.replace(tzinfo=timezone.utc)

    if isinstance(raw_val, (int, float)):
        try:
            # Handle epoch in milliseconds vs seconds
            ts = raw_val / 1000.0 if raw_val > 1e11 else float(raw_val)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return now

    s = str(raw_val).strip()
    if not s:
        return now

    s_lower = s.lower()

    # Immediate / current indicators
    if s_lower in ('just now', 'recent', 'recently', 'today', 'recent post', 'moment ago', 'few seconds ago'):
        return now

    # Relative time expressions: e.g. "30 minutes ago", "2 hours ago", "3d ago", "1 week ago", "2 mo ago"
    rel_match = re.match(r'(\d+)\s*(minute|min|m|hour|hr|h|day|d|week|w|month|mo)\w*\s*ago', s_lower)
    if rel_match:
        val = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit.startswith('m') and not unit.startswith('mo'):
            return now - timedelta(minutes=val)
        elif unit.startswith('h'):
            return now - timedelta(hours=val)
        elif unit.startswith('d'):
            return now - timedelta(days=val)
        elif unit.startswith('w'):
            return now - timedelta(weeks=val)
        elif unit.startswith('mo'):
            return now - timedelta(days=val * 30)

    if 'yesterday' in s_lower:
        return now - timedelta(days=1)

    # Native ISO 8601 parsing (supports Python 3.11+)
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    # Common standard calendar formats
    calendar_formats = (
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%b %d, %Y',
        '%B %d, %Y',
        '%Y-%m-%d %H:%M:%S',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%a, %d %b %Y %H:%M:%S %z'
    )
    for fmt in calendar_formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt
        except ValueError:
            pass

    return now
