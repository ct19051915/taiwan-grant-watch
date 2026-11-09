import argparse
import json
import logging
from .export import export_rows
from .service import collect, load_sources
from .storage import Store


def main():
    parser = argparse.ArgumentParser(description='台灣企業補助公告追蹤（第一階段）')
    parser.add_argument('--sources', default='data/sources.json')
    parser.add_argument('--db', default='var/grants.sqlite3')
    parser.add_argument('--log-file', help='選填 UTF-8 日誌路徑；預設 stderr')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('sources', help='同步並列出候選來源及執行驗證狀態')
    fetch = sub.add_parser('fetch', help='擷取明確選定且已人工確認規範的來源')
    fetch.add_argument('--source', action='append', required=True)
    export = sub.add_parser('export')
    export.add_argument('path')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, filename=args.log_file, encoding='utf-8',
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    store = Store(args.db)
    try:
        sources = load_sources(args.sources)
        store.sync_sources(sources)
        if args.command == 'sources':
            print(json.dumps(store.sources(), ensure_ascii=False, indent=2))
        elif args.command == 'fetch':
            missing = set(args.source) - {s['id'] for s in sources}
            if missing:
                parser.error('未知來源 ID: ' + ','.join(sorted(missing)))
            result = collect(store, [s for s in sources if s['id'] in args.source])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return int(any('error' in value for value in result.values()))
        else:
            export_rows(store.announcements(), args.path)
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
