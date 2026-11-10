"""來源名冊與目前資料庫的涵蓋統計，零筆與尚未追蹤分開。"""


def coverage_rows(catalog, sources):
    actual = {s['id']: s for s in sources}
    result = []
    for source in catalog:
        live = actual.get(source['id'], {})
        enabled = source.get('enabled', False)
        config = live.get('config', {})
        matching = all(config.get(k) == source.get(k) for k in
                       ('url', 'method', 'parser', 'detail_selector', 'detail_fields', 'detail_exclude_selectors', 'detail_ignored_line_patterns', 'allow_empty'))
        verified = enabled and matching and live.get('validation_status') == 'verified' and bool(live.get('last_success_at'))
        result.append(dict(id=source['id'], agency=source['agency'], level=source['government_level'],
                           city=source.get('city'), url=source['url'], method=source['method'],
                           enabled=enabled, verified=verified,
                           announcement_count=live.get('announcement_count', 0),
                           last_outcome=live.get('last_outcome'),
                           reason=source.get('unsupported_reason') or source.get('last_error')))
    return result


def coverage_summary(rows):
    return {level: dict(total=len(group), enabled=sum(r['enabled'] for r in group),
                        verified=sum(r['verified'] for r in group))
            for level in ('central', 'local')
            for group in [[r for r in rows if r['level'] == level]]}
