def fetch_realtime_news(stock_name):
    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            headlines = []
            
            # 방송 영상 클립 및 단순 사진 기사 블랙리스트
            junk_keywords = ['자막뉴스', '현장영상', '영상뉴스', '다시보기', '풀영상', '포토', '카드뉴스']

            for item in items:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = title_el.text

                    # 1. 자막뉴스 등 방송 영상 찌꺼기는 통째로 패스
                    if any(junk in title for junk in junk_keywords):
                        continue

                    # 2. HTML 태그 제거
                    title = re.sub(r'<[^>]+>', '', title)

                    # 3. 제목 끝 언론사 출처 제거 (- 머니투데이, | 한국경제 등)
                    title = re.sub(r'\s*[-–—|]\s*[^-–—|]+$', '', title)

                    # 4. 모든 대괄호 [ ] 및 그 안의 글자 도려내기
                    title = re.sub(r'\[.*?\]', '', title)

                    # 5. 따옴표, 불필요한 기호 및 양쪽 공백 정리
                    clean = title.strip().strip('"\'“”')

                    # 정제 후 15자 이상의 유의미한 제목만 2개 수집
                    if len(clean) >= 15:
                        headlines.append(clean)
                    
                    if len(headlines) == 2:
                        break

            return headlines
    except Exception:
        return []
