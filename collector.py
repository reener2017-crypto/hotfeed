# 핫피드 수집기 — stdlib만 사용 (pip 설치 불필요)
# 소스별 실패가 전체를 죽이지 않도록 각각 try/except, 실패 시 기존 데이터 유지
import json, re, sys, time, html as H
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
KST = timezone(timedelta(hours=9))
NOW = int(time.time())
DATA_PATH = 'data.json'
LIMIT = 15

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(t):
    t = H.unescape(re.sub(r'<[^>]+>', '', t or ''))
    return re.sub(r'\s+', ' ', t).strip()

def item(source, board, title, url, ts):
    return {'source': source, 'board': board, 'title': title, 'url': url, 'ts': ts}

def src_yna():
    raw = fetch('https://www.yna.co.kr/rss/news.xml')
    root = ET.fromstring(raw)
    out = []
    for it in root.iter('item'):
        t, link, pub = it.findtext('title'), it.findtext('link'), it.findtext('pubDate')
        if not t or not link: continue
        try: ts = int(parsedate_to_datetime(pub).timestamp())
        except Exception: ts = NOW
        out.append(item('연합뉴스', '최신 기사', t.strip(), link.strip(), ts))
        if len(out) >= 30: break
    return out

def src_ou():
    raw = fetch('https://www.todayhumor.co.kr/board/list.php?table=bestofbest').decode('utf-8', 'ignore')
    out, seen = [], set()
    for url, t in re.findall(r'<a href="(/board/view\.php\?table=bestofbest&no=\d+[^"]*)"[^>]*>(.*?)</a>', raw):
        t = clean(t)
        if not t or url in seen: continue
        seen.add(url)
        out.append(item('오늘의유머', '베스트오브베스트', t, 'https://www.todayhumor.co.kr' + url, NOW))
        if len(out) >= LIMIT: break
    return out

def src_bobae():
    raw = fetch('https://www.bobaedream.co.kr/list?code=best').decode('utf-8', 'ignore')
    out, seen = [], set()
    for url, t in re.findall(r'<a class="bsubject"[^>]*href="(/view\?code=best&No=\d+[^"]*)"[^>]*title="([^"]*)"', raw):
        t = clean(t)
        if not t or url in seen: continue
        seen.add(url)
        out.append(item('보배드림', '베스트글', t, 'https://www.bobaedream.co.kr' + url, NOW))
        if len(out) >= LIMIT: break
    return out

def src_ruli():
    raw = fetch('https://bbs.ruliweb.com/best/hit_history').decode('utf-8', 'ignore')
    out, seen = [], set()
    for url, t in re.findall(r'<a[^>]+href="(/(?:[a-z]+)/board/\d+/read/\d+[^"]*)"[^>]*>(.*?)</a>', raw, re.S):
        t = clean(t)
        if len(t) < 4 or url in seen: continue
        seen.add(url)
        out.append(item('루리웹', '베스트', t, 'https://bbs.ruliweb.com' + url, NOW))
        if len(out) >= LIMIT: break
    return out

def src_pann():
    raw = fetch('https://pann.nate.com/talk/ranking').decode('utf-8', 'ignore')
    out, seen = [], set()
    for pid, t in re.findall(r'<h2><a href="(/talk/\d+)"[^>]*title="([^"]*)"', raw):
        t = clean(t)
        if not t or pid in seen: continue
        seen.add(pid)
        out.append(item('네이트판', '베스트톡 랭킹', t, 'https://pann.nate.com' + pid, NOW))
        if len(out) >= LIMIT: break
    return out

SOURCES = [('연합뉴스', src_yna), ('오늘의유머', src_ou), ('보배드림', src_bobae), ('루리웹', src_ruli), ('네이트판', src_pann)]

def main():
    old = {}
    try:
        prev = json.load(open(DATA_PATH, encoding='utf-8'))
        for it in prev.get('items', []):
            old.setdefault(it['source'], []).append(it)
    except Exception:
        pass

    fresh = {}
    for name, fn in SOURCES:
        try:
            got = fn()
            if got: fresh[name] = got
            print(f'[OK] {name}: {len(got)}건')
        except Exception as e:
            print(f'[FAIL] {name}: {e}', file=sys.stderr)
    for name, _ in SOURCES:
        if name not in fresh and name in old:
            fresh[name] = old[name]
            print(f'[KEEP] {name}: 기존 데이터 유지')

    news = sorted(fresh.get('연합뉴스', []), key=lambda x: -x['ts'])
    comm_by_site = [fresh.get(n, []) for n in ('오늘의유머', '보배드림', '루리웹', '네이트판')]
    comm, idx = [], 0
    while any(idx < len(s) for s in comm_by_site):
        for s in comm_by_site:
            if idx < len(s): comm.append(s[idx])
        idx += 1

    feed, ci = [], 0
    for i, n in enumerate(news):
        feed.append(n)
        if i % 2 == 1:
            for _ in range(2):
                if ci < len(comm): feed.append(comm[ci]); ci += 1
    feed.extend(comm[ci:])

    data = {'updated_at': datetime.fromtimestamp(NOW, KST).strftime('%Y-%m-%d %H:%M'), 'items': feed}
    json.dump(data, open(DATA_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'총 {len(feed)}건 저장')

if __name__ == '__main__':
    main()
