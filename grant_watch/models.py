from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_date(value: str | None) -> str | None:
    """只接受明確完整日期；民國日期須有民國標記或三位數年份。"""
    if not value:
        return None
    value = value.strip()
    m = re.fullmatch(r'(民國)?\s*(\d{2,4})[年/.-](\d{1,2})[月/.-](\d{1,2})日?', value)
    if m:
        year, month, day = map(int, m.groups()[1:])
        if m[1] or len(m[2]) == 3:
            year += 1911
        elif len(m[2]) != 4:
            return None
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            return None


def canonical_url(value: str) -> str:
    p = urlsplit(value)
    if p.scheme.lower() not in {'http', 'https'} or not p.hostname or p.username or p.password:
        raise ValueError('公告網址必須是無登入資訊的 HTTP(S) URL')
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urlencode(sorted(query)), ''))


@dataclass
class Announcement:
    title: str
    agency: str
    government_level: str
    city: str | None
    official_url: str
    external_id: str | None = None
    announced_on: str | None = None
    deadline: str | None = None
    amount: str | None = None
    eligibility: str | None = None
    category: str | None = None
    content: str | None = None

    def normalized(self):
        result = asdict(self)
        result['title'] = ' '.join(self.title.split())
        if not result['title']:
            raise ValueError('公告標題不可為空')
        result['official_url'] = canonical_url(self.official_url)
        for field in ('announced_on', 'deadline'):
            result[field] = parse_date(result[field])
        for key, value in result.items():
            if isinstance(value, str):
                result[key] = value.strip() or None
        return result

    def fingerprint(self):
        fields = self.normalized()
        # URL 與上游識別碼另行比對；雜湊不含擷取時間。
        fields.pop('official_url')
        fields.pop('external_id')
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
