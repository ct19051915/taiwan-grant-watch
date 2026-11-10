"""主題標籤與企業補助判定分開；只匹配官方文字並保留命中字詞。"""
import re

RULES = {
    'AI': r'(?<![A-Za-z])AI(?![A-Za-z])|人工智慧|人工智能',
    '智慧製造': r'智慧製造|智慧工廠|工業4\.0|智慧機械',
    '數位轉型': r'數位轉型|數位升級|數位化|數位創新',
    '節能減碳': r'節能|減碳|淨零|低碳|碳中和|溫室氣體減量',
    '研發創新': r'研發|創新|技術開發|SBIR|A\+計畫',
}


def classify_topics(title, document):
    text = title or ''
    if not document.get('error') and document.get('http_status') == 200:
        text += '\n' + (document.get('body') or '')
    evidence = {label: list(dict.fromkeys(re.findall(pattern, text, re.I)))
                for label, pattern in RULES.items()}
    return {label: words for label, words in evidence.items() if words}
