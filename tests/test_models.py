import pytest
from grant_watch.models import parse_date, canonical_url


@pytest.mark.parametrize(('raw', 'expected'), [
    ('115/11/09', '2026-11-09'), ('民國99年1月2日', '2010-01-02'),
    ('2026-11-09', '2026-11-09'), ('2026年11月9日', '2026-11-09'),
    ('2026-11-09T08:00:00+08:00', '2026-11-09'),
    ('Mon, 09 Nov 2026 08:00:00 +0800', '2026-11-09'),
    ('2024/2/29', '2024-02-29'), ('2025/2/29', None),
    ('115/13/1', None), ('即日起', None), ('11/09', None),
    ('26/11/09', None), ('', None), (None, None),
])
def test_dates(raw, expected):
    assert parse_date(raw) == expected


def test_canonical():
    assert canonical_url('https://UNIT.gov.tw/n?z=2&utm_source=x&a=1#part') == 'https://unit.gov.tw/n?a=1&z=2'
    assert canonical_url('https://unit.gov.tw/n?id=1') != canonical_url('https://unit.gov.tw/n?id=2')


@pytest.mark.parametrize('url', ['javascript:alert(1)', '/relative', 'https://user:password@unit.gov.tw/'])
def test_bad_urls(url):
    with pytest.raises(ValueError):
        canonical_url(url)
