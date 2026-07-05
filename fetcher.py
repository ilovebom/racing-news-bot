"""
赛车资讯抓取模块
支持 F1、NASCAR、MotoGP、WRC、中国GT、国内赛车等
改进：多源冗余、自动过滤广告、获取完整正文、网络错误降级
新增：Autosport、Racer.com、Formula1官方、NASCAR、国内赛车等
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
from typing import List, Dict
from urllib.parse import urljoin

# ============================================================
# 新闻源配置
# ============================================================

# --------------------
# F1 新闻源（多个RSS + 网页备份）
# --------------------
F1_RSS_SOURCES = [
    {
        "name": "BBC Sport F1",
        "url": "http://feeds.bbci.co.uk/sport/rss/f1/rss.xml",
        "lang": "en",
        "category": "F1",
    },
    {
        "name": "Motorsport F1",
        "url": "https://www.motorsport.com/rss/f1/",
        "lang": "en",
        "category": "F1",
    },
    {
        "name": "Autosport F1",
        "url": "https://www.autosport.com/rss/f1/",
        "lang": "en",
        "category": "F1",
    },
    {
        "name": "Racer.com F1",
        "url": "https://racer.com/category/f1/feed/",
        "lang": "en",
        "category": "F1",
    },
    {
        "name": "Formula1.com 官方",
        "url": "https://www.formula1.com/en/latest.rss",
        "lang": "en",
        "category": "F1",
    },
]

# F1 网页备份源（RSS 失败时的备用）
F1_WEB_SOURCES = [
    {
        "name": "BBC Sport F1 网页",
        "url": "https://www.bbc.com/sport/formula1",
        "category": "F1",
        "selectors": ["[data-testid='card-headline']", "h3", "h2"],
    },
    {
        "name": "Motorsport F1 网页",
        "url": "https://www.motorsport.com/f1/",
        "category": "F1",
        "selectors": ["article a", ".news-item a", ".article-title a", "h3 a", "h2 a"],
    },
]

# --------------------
# NASCAR 新闻源
# --------------------
NASCAR_RSS_SOURCES = [
    {
        "name": "NASCAR 官方新闻",
        "url": "https://www.nascar.com/rss/news/",
        "lang": "en",
        "category": "NASCAR",
    },
    {
        "name": "Jayski NASCAR",
        "url": "https://www.jayski.com/feed/",
        "lang": "en",
        "category": "NASCAR",
    },
]

NASCAR_WEB_SOURCES = [
    {
        "name": "NASCAR 官网网页",
        "url": "https://www.nascar.com/news-media/",
        "category": "NASCAR",
        "selectors": ["article a", ".news-item a", "h3 a", "h2 a"],
    },
]

# --------------------
# MotoGP 新闻源
# --------------------
MOTOGP_RSS_SOURCES = [
    {
        "name": "MotoGP 官方",
        "url": "https://www.motogp.com/en/news/rss",
        "lang": "en",
        "category": "MotoGP",
    },
    {
        "name": "Motorsport MotoGP",
        "url": "https://www.motorsport.com/rss/motogp/",
        "lang": "en",
        "category": "MotoGP",
    },
]

# --------------------
# WRC（世界拉力锦标赛）新闻源
# --------------------
WRC_RSS_SOURCES = [
    {
        "name": "WRC 官方",
        "url": "https://www.wrc.com/en/news/rss",
        "lang": "en",
        "category": "WRC",
    },
]

# --------------------
# 国内赛车新闻源（网页抓取，部分源可能需要调整）
# --------------------
CHINA_RACING_WEB_SOURCES = [
    {
        "name": "腾讯赛车",
        "url": "https://sports.qq.com/racing/",
        "category": "国内赛车",
        "selectors": [".news-item a", ".news-list a", "h3 a", "h2 a"],
    },
]

# --------------------
# 中国GT / 澳门格兰披治 / 其他国内赛事（部分源可能需要调整）
# --------------------
CHINA_GT_SOURCES = [
    {
        "name": "ChinaGT官网",
        "url": "http://www.chinagt.net/news/",
        "category": "中国GT",
        "selectors": [".news-item", ".article-item", "li.news", ".list-item", ".news-list li", "article", ".post"],
    },
]

# ============================================================
# 广告/垃圾内容过滤关键词
# ============================================================

AD_KEYWORDS = [
    "电话", "传真", "邮箱", "地址", "联系", "推广",
    "唯一推广", "隶属于", "有限公司", "广告",
    "Copyright", "版权所有", "备案号", "ICP",
    "Tel:", "Fax:", "Email:", "Contact:",
    "Powered by", "免责声明", "隐私政策",
    "点击这里", "立即注册", "免费试用", "优惠",
    "赌场", "彩票", "赌博", "casino", "bet365",
    # 新增：非新闻内容过滤
    "official partners", "official partner", "partners list", "partner list",
    "赞助商列表", "合作伙伴列表", "官方合作伙伴", "赞助商名单",
    "become a sponsor", "sponsorship opportunities", "sponsor us",
    "our sponsors", "proud sponsors", "title sponsor", "presenting sponsor",
    "官方赞助商", "冠名赞助商", "合作伙伴招募", "商务合作",
    "advertise with us", "advertising", "广告合作",
]

BAD_TITLE_PATTERNS = [
    r'^电话', r'^传真', r'^邮箱', r'^地址', r'^联系',
    r'^关于我们', r'^关于\b', r'^首页', r'^\d{3,4}-\d{7,8}',
    r'^联系我们', r'^公司简介', r'^导航$', r'^当前位置',
    # 新增：过滤非新闻标题
    r'official\s*partner', r'our\s*sponsors', r'sponsor\s*list',
    r'partner\s*list', r'become\s*a\s*sponsor', r'sponsorship',
    r'合作伙伴$', r'赞助商$', r'合作伙伴列表', r'赞助商列表',
    r'^advertis', r'^广告', r'^商务合作',
]

# 非新闻内容判断：如果标题包含这些词，且正文很短，则判定为非新闻
NON_NEWS_TITLE_KEYWORDS = [
    "official partners", "partners", "sponsors", "sponsor",
    "官方合作伙伴", "合作伙伴", "赞助商", "赞助商名单",
    "advertise", "advertising", "广告", "商务合作",
    "about us", "about", "关于我们", "关于",
    "contact us", "联系我们", "contact",
    "privacy policy", "privacy", "隐私政策",
    "terms of use", "terms", "使用条款",
    "careers", "jobs", "招聘", "加入我们",
    "media kit", "press kit", "媒体资料",
]


def is_ad_or_spam(title: str, summary: str = "") -> bool:
    """判断是否为广告、垃圾内容或非新闻内容"""
    text = (title + " " + summary).lower()

    for kw in AD_KEYWORDS:
        if kw.lower() in text:
            return True

    for pattern in BAD_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    if re.search(r'\d{3,4}-\d{7,8}', text):
        return True

    if len(summary) < 50 and any(kw in summary for kw in ["电话", "邮箱", "地址"]):
        return True

    # 过滤纯大写英文标题（通常是广告或标签页）
    if title.isupper() and len(title) > 20:
        return True

    # 新增：过滤合作伙伴/赞助商列表等非新闻内容
    # 如果标题中包含明显的非新闻关键词，直接过滤
    title_lower = title.lower()
    for kw in NON_NEWS_TITLE_KEYWORDS:
        if kw.lower() in title_lower:
            # 如果是合作伙伴列表类，摘要很短且没有实质性内容，则判定为广告
            if len(summary) < 200 or "official" in title_lower or "partner" in title_lower or "sponsor" in title_lower:
                return True

    return False


def is_non_news_page(content_text: str, title: str = "") -> bool:
    """
    判断页面内容是否为非新闻页面（如合作伙伴列表、赞助商页等）
    返回 True 表示这是非新闻内容，应该跳过
    """
    if not content_text:
        return True

    text_lower = content_text.lower()
    title_lower = title.lower()

    # 检查标题是否包含明显的非新闻关键词
    non_news_keywords = [
        "official partners", "our partners", "our sponsors", "partner list",
        "sponsor list", "become a sponsor", "sponsorship opportunities",
        "official sponsor", "title sponsor", "presenting sponsor",
        "advertise with us", "advertising", "media kit", "press kit",
    ]
    for kw in non_news_keywords:
        if kw in title_lower:
            return True

    # 检查内容是否是列表/罗列型（比如罗列几十个赞助商名称）
    # 特征：大量 "official" 或品牌名称连续出现
    official_count = text_lower.count("official")
    # 如果 "official" 出现超过 5 次，很可能是合作伙伴列表页
    if official_count >= 5:
        return True

    # 检查内容中是否主要是品牌名称列表（短句+换行/逗号分隔）
    lines = content_text.split('\n')
    short_brand_lines = 0
    for line in lines:
        line = line.strip()
        # 短行（3-30个字符），且看起来像品牌名称（纯英文或包含®、™）
        if 3 <= len(line) <= 50 and (line.isalpha() or '®' in line or '™' in line or 'official' in line.lower()):
            short_brand_lines += 1
    # 如果超过 50% 的行都是短品牌名称，判定为列表页
    if len(lines) > 10 and short_brand_lines / len(lines) > 0.5:
        return True

    # 检查内容是否过短（少于 200 字且没有新闻要素）
    if len(content_text) < 200:
        # 检查是否有新闻特征词
        news_indicators = ["said", "said", "announced", "reported", "won", "victory",
                          "race", "championship", "season", "driver", "team",
                          "比赛", "冠军", "赛季", "车手", "车队", "宣布", "报道"]
        has_news_indicator = any(ind in text_lower for ind in news_indicators)
        if not has_news_indicator:
            return True

    return False


# ============================================================
# 已发布新闻记录（去重用，避免重复发布昨天的内容）
# ============================================================

PUBLISHED_HISTORY_FILE = "published_history.json"
HISTORY_MAX_DAYS = 30  # 只保留最近30天的记录


def normalize_title(title: str) -> str:
    """标准化标题：去掉标点、空格、大小写，用于模糊匹配"""
    import re
    # 转小写，去掉所有标点符号和多余空格
    s = title.lower()
    s = re.sub(r'[^\w\s]', '', s)  # 去掉标点
    s = re.sub(r'\s+', ' ', s).strip()  # 合并空格
    return s


def load_published_history() -> set:
    """加载已发布过的新闻标题集合（标准化后）"""
    try:
        if os.path.exists(PUBLISHED_HISTORY_FILE):
            with open(PUBLISHED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # data 格式: {"2026-07-04": ["标题1", "标题2", ...], ...}
                # 只保留最近 HISTORY_MAX_DAYS 天的
                cutoff_date = (datetime.now() - timedelta(days=HISTORY_MAX_DAYS)).strftime("%Y-%m-%d")
                titles = set()
                for date_str, title_list in data.items():
                    if date_str >= cutoff_date:
                        for t in title_list:
                            titles.add(normalize_title(t))  # 标准化后存储
                print(f"[去重] 已加载 {len(titles)} 条已发布新闻记录")
                return titles
    except Exception as e:
        print(f"[去重] 加载已发布记录失败（首次运行正常）：{e}")
    return set()


def save_published_history(news_list: list):
    """保存今天发布的新闻标题到历史记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # 读取已有记录
        data = {}
        if os.path.exists(PUBLISHED_HISTORY_FILE):
            with open(PUBLISHED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        # 今天的新标题（原始标题，用于展示）
        today_titles = []
        for news in news_list:
            t = news.get("title", "").strip()
            t_zh = news.get("title_zh", "").strip()
            if t:
                today_titles.append(t)
            if t_zh and t_zh != t:
                today_titles.append(t_zh)

        # 更新今天的记录
        data[today] = today_titles

        # 清理超过30天的旧记录
        cutoff_date = (datetime.now() - timedelta(days=HISTORY_MAX_DAYS)).strftime("%Y-%m-%d")
        data = {k: v for k, v in data.items() if k >= cutoff_date}

        # 保存
        os.makedirs(os.path.dirname(PUBLISHED_HISTORY_FILE), exist_ok=True)
        with open(PUBLISHED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[去重] 已保存 {len(today_titles)} 条今日发布记录到历史")
    except Exception as e:
        print(f"[去重] 保存发布记录失败：{e}")


def filter_published_news(news_list: List[Dict], published_titles: set) -> List[Dict]:
    """过滤掉已经发布过的新闻（模糊匹配标题）"""
    if not published_titles:
        return news_list

    filtered = []
    skipped = 0
    for news in news_list:
        title = news.get("title", "").strip()
        title_zh = news.get("title_zh", "").strip()

        # 用标准化后的标题检查
        title_norm = normalize_title(title)
        title_zh_norm = normalize_title(title_zh) if title_zh else ""

        # 检查是否匹配（原始或标准化）
        matched = False
        for published_norm in published_titles:
            if title_norm == published_norm:
                matched = True
                break
            if title_zh_norm and title_zh_norm == published_norm:
                matched = True
                break
            # 额外检查：如果标准化后的标题前30个字符相同，也认为是重复
            if title_norm and published_norm and title_norm[:30] == published_norm[:30] and len(title_norm) > 20:
                matched = True
                break

        if matched:
            skipped += 1
            if skipped <= 3:  # 只打印前3条跳过的新闻，避免刷屏
                print(f"[去重] 跳过已发布：{title[:40]}...")
        else:
            filtered.append(news)

    if skipped > 0:
        print(f"[去重] 共过滤掉 {skipped} 条已发布过的新闻")
    return filtered


# ============================================================
# 通用 RSS 抓取函数
# ============================================================

def fetch_rss_generic(rss_sources: List[Dict], max_age_days: int = 7, max_per_source: int = 15) -> List[Dict]:
    """通用 RSS 抓取函数，支持多个新闻源"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for source in rss_sources:
        try:
            print(f"[RSS] 正在抓取：{source['name']}")
            feed = feedparser.parse(source["url"])

            if not feed.entries:
                print(f"[RSS] 警告：{source['name']} 没有返回条目")
                continue

            print(f"[RSS] {source['name']} 返回 {len(feed.entries)} 条原始条目")

            for entry in feed.entries[:max_per_source]:
                # 解析发布时间
                pub_time = None
                for time_attr in ["published_parsed", "updated_parsed", "created_parsed"]:
                    if hasattr(entry, time_attr) and getattr(entry, time_attr):
                        try:
                            pub_time = datetime(*getattr(entry, time_attr)[:6])
                            break
                        except Exception:
                            pass

                if not pub_time:
                    pub_time = datetime.now() - timedelta(days=1)

                # 只保留最近 N 天的新闻
                if pub_time < cutoff:
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                # 清理 RSS 摘要中的 HTML 标签
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()

                # 过滤广告
                if is_ad_or_spam(title, summary):
                    print(f"[RSS] 跳过广告：{title[:30]}...")
                    continue

                # 过滤空标题
                if len(title) < 5:
                    continue

                news = {
                    "title": title,
                    "title_zh": "",
                    "summary": summary[:500],
                    "link": entry.get("link", ""),
                    "pub_time": pub_time.isoformat(),
                    "source": source["name"],
                    "category": source.get("category", "赛车"),
                    "lang": source.get("lang", "en"),
                    "image": "",
                    "full_content": "",
                }

                # 提取图片
                if hasattr(entry, "media_content") and entry.media_content:
                    news["image"] = entry.media_content[0].get("url", "")
                elif hasattr(entry, "links"):
                    for link in entry.links:
                        if link.get("type", "").startswith("image"):
                            news["image"] = link.get("href", "")
                            break
                if not news["image"] and hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image"):
                            news["image"] = enc.get("href", "")
                            break

                all_news.append(news)
                print(f"[RSS] ✓ 抓取到：{title[:50]}...")

        except Exception as e:
            print(f"[RSS] 抓取失败 {source['name']}: {e}")

    print(f"[RSS] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 通用网页抓取函数
# ============================================================

def fetch_web_generic(web_sources: List[Dict], max_age_days: int = 7, max_per_source: int = 10) -> List[Dict]:
    """通用网页抓取函数"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for source in web_sources:
        try:
            print(f"[Web] 正在抓取：{source['name']}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            resp = requests.get(source["url"], headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            selectors = source.get("selectors", ["article a", "h3 a", "h2 a"])
            articles = []
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    articles = items
                    print(f"[Web] {source['name']} 找到 {len(items)} 条候选（选择器：{selector}）")
                    break

            if not articles:
                # 兜底：找所有包含链接的元素
                all_links = soup.select("a")
                for link in all_links:
                    text = link.get_text(strip=True)
                    if len(text) > 15 and len(text) < 150:
                        articles.append(link)
                if articles:
                    print(f"[Web] {source['name']} 通过兜底找到 {len(articles)} 条候选")

            for article in articles[:max_per_source]:
                if article.name == "a":
                    a_tag = article
                else:
                    a_tag = article.find_parent("a") or article.find("a")

                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag.get("href", "")

                if not title or len(title) < 10:
                    continue

                # 处理相对链接
                if link and not link.startswith("http"):
                    link = urljoin(source["url"], link)

                # 过滤广告
                if is_ad_or_spam(title):
                    continue

                all_news.append({
                    "title": title,
                    "title_zh": "",
                    "summary": "",
                    "link": link,
                    "pub_time": datetime.now().isoformat(),
                    "source": source["name"],
                    "category": source.get("category", "赛车"),
                    "lang": "zh" if "zh" in source.get("url", "") or "sina" in source.get("url", "") or "qq" in source.get("url", "") else "en",
                    "image": "",
                    "full_content": "",
                })
                print(f"[Web] ✓ 抓取到：{title[:50]}...")

        except Exception as e:
            print(f"[Web] 抓取失败 {source['name']}: {e}")

    print(f"[Web] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# F1 新闻抓取（保留原有函数，调用通用函数）
# ============================================================

def fetch_f1_rss() -> List[Dict]:
    """从 RSS 源抓取 F1 新闻（只抓最近48小时）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    return fetch_rss_generic(F1_RSS_SOURCES, max_age_days=days, max_per_source=15)


def fetch_f1_web_backup() -> List[Dict]:
    """从网页抓取 F1 新闻作为备份（只抓最近48小时）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    return fetch_web_generic(F1_WEB_SOURCES, max_age_days=days, max_per_source=10)


# ============================================================
# NASCAR 新闻抓取
# ============================================================

def fetch_nascar_news() -> List[Dict]:
    """抓取 NASCAR 新闻（只抓最近48小时）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    print("\n[NASCAR] 开始抓取 NASCAR 新闻...")
    news = fetch_rss_generic(NASCAR_RSS_SOURCES, max_age_days=days, max_per_source=10)
    if not news:
        print("[NASCAR] RSS 未获取到新闻，尝试网页备份...")
        news = fetch_web_generic(NASCAR_WEB_SOURCES, max_age_days=days, max_per_source=8)
    return news


# ============================================================
# MotoGP / WRC 新闻抓取
# ============================================================

def fetch_motogp_news() -> List[Dict]:
    """抓取 MotoGP 新闻（只抓最近48小时）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    print("\n[MotoGP] 开始抓取 MotoGP 新闻...")
    return fetch_rss_generic(MOTOGP_RSS_SOURCES, max_age_days=days, max_per_source=10)


def fetch_wrc_news() -> List[Dict]:
    """抓取 WRC 新闻（只抓最近48小时）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    print("\n[WRC] 开始抓取 WRC 新闻...")
    return fetch_rss_generic(WRC_RSS_SOURCES, max_age_days=days, max_per_source=10)


# ============================================================
# 国内赛车新闻抓取
# ============================================================

def fetch_china_racing_news() -> List[Dict]:
    """抓取国内赛车新闻（放宽到72小时，因为国内赛事更新频率低）"""
    import os
    days = int(os.getenv("NEWS_MAX_AGE_DAYS_CN", "3"))
    print("\n[国内赛车] 开始抓取国内赛车新闻...")
    return fetch_web_generic(CHINA_RACING_WEB_SOURCES, max_age_days=days, max_per_source=8)


# ============================================================
# 中国 GT / 澳门格兰披治等
# ============================================================

def fetch_china_gt_news() -> List[Dict]:
    """抓取中国 GT 新闻（放宽到72小时）"""
    import os
    cn_days = int(os.getenv("NEWS_MAX_AGE_DAYS_CN", "3"))
    all_news = []
    cutoff = datetime.now() - timedelta(days=cn_days)

    for source in CHINA_GT_SOURCES:
        try:
            print(f"[中国GT/澳门] 正在抓取：{source['name']}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            resp = requests.get(source["url"], headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            print(f"[中国GT/澳门] 页面标题：{soup.title.string if soup.title else 'N/A'}")
            print(f"[中国GT/澳门] 页面大小：{len(resp.text)} 字符")

            # 尝试多种选择器找到新闻列表
            news_items = []
            selectors = source.get("selectors", [
                ".news-item", ".article-item", "li.news", ".list-item",
                ".news-list li", ".article-list li", ".list li",
                ".items .item", ".newsbox .news", ".news li",
                "article", ".post", ".entry",
            ])
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    news_items = items
                    print(f"[中国GT/澳门] 找到 {len(items)} 条新闻（选择器：{selector}）")
                    break

            # 如果没找到，尝试直接找所有包含链接的元素
            if not news_items:
                all_links = soup.select("a")
                for link in all_links:
                    text = link.get_text(strip=True)
                    if len(text) > 10 and len(text) < 100 and any(kw in text for kw in ["GT", "赛车", "比赛", "站", "冠军", "车队", "车手", "大赛车"]):
                        news_items.append(link)
                if news_items:
                    print(f"[中国GT/澳门] 通过文本匹配找到 {len(news_items)} 条新闻")

            for item in news_items[:10]:
                # 获取标题和链接
                if item.name == "a":
                    a_tag = item
                    title = item.get_text(strip=True)
                else:
                    a_tag = item.select_one("a")
                    if not a_tag:
                        continue
                    title = a_tag.get_text(strip=True)

                link = a_tag.get("href", "") if a_tag else ""

                if not title or len(title) < 5 or len(title) > 200:
                    continue

                # 过滤广告
                if is_ad_or_spam(title):
                    print(f"[中国GT/澳门] 跳过广告：{title[:30]}...")
                    continue

                # 处理相对链接
                if link and not link.startswith("http"):
                    link = urljoin(source["url"], link)

                # 获取发布时间
                date_tag = item.select_one(".date, .time, .pubtime, time, .datetime") if item.name != "a" else None
                pub_time = datetime.now() - timedelta(days=1)
                if date_tag:
                    date_str = date_tag.get_text(strip=True)
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%Y-%m-%d %H:%M", "%Y年%m月%d日"]:
                        try:
                            pub_time = datetime.strptime(date_str, fmt)
                            if pub_time.year < 2020:
                                pub_time = pub_time.replace(year=datetime.now().year)
                            break
                        except Exception:
                            continue

                if pub_time < cutoff:
                    continue

                # 获取图片
                img = item.select_one("img") if item.name != "a" else None
                image = img.get("src", "") if img else ""
                if image and not image.startswith("http"):
                    image = urljoin(source["url"], image)

                all_news.append({
                    "title": title,
                    "title_zh": title,
                    "summary": "",
                    "link": link,
                    "pub_time": pub_time.isoformat(),
                    "source": source["name"],
                    "category": source.get("category", "中国GT"),
                    "lang": "zh",
                    "image": image,
                    "full_content": "",
                })
                print(f"[中国GT/澳门] ✓ 抓取到：{title[:50]}...")

                if len(all_news) >= 8:
                    break

        except Exception as e:
            print(f"[中国GT/澳门] 抓取失败 {source['name']}: {e}")

    print(f"[中国GT/澳门] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 新闻详情补充（抓取完整正文）
# ============================================================

def enrich_news_detail(news_list: List[Dict]) -> List[Dict]:
    """补充新闻详情（完整正文、图片），并过滤非新闻内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    valid_news = []
    for news in news_list:
        if not news.get("link"):
            valid_news.append(news)
            continue

        try:
            resp = requests.get(news["link"], headers=headers, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. 提取正文（完整，不截断）
            content_text = ""
            content_selectors = [
                "article", "#article-content", ".article-content",
                ".content", "#content", ".post-content",
                "#news-content", ".news-content", ".detail-content",
                "[class*='article']", "[class*='content']",
                ".entry-content", ".post-body",
            ]
            for selector in content_selectors:
                content_el = soup.select_one(selector)
                if content_el:
                    content_text = content_el.get_text(separator='\n', strip=True)
                    break

            # 如果没找到，尝试所有段落
            if not content_text:
                paragraphs = soup.select("p")
                content_text = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])

            # 清理内容
            content_text = re.sub(r'\n+', '\n', content_text).strip()
            content_text = re.sub(r'\s+', ' ', content_text).strip()

            # 2. 检查是否为非新闻页面（如合作伙伴列表、赞助商页等）
            if is_non_news_page(content_text, news.get("title", "")):
                print(f"[详情] ⚠️ 跳过非新闻内容：{news['title'][:40]}...（合作伙伴/赞助商列表等）")
                continue

            # 保存完整内容
            news["full_content"] = content_text[:3000]

            # 如果 RSS 没有摘要，从正文生成
            if not news.get("summary") or len(news.get("summary", "")) < 50:
                news["summary"] = content_text[:500] if len(content_text) > 50 else ""

            # 3. 提取封面图
            if not news.get("image"):
                img_selectors = [
                    "article img", ".article-content img", ".content img",
                    "#content img", ".post-content img", "meta[property='og:image']",
                    ".entry-content img",
                ]
                for selector in img_selectors:
                    if selector.startswith("meta"):
                        meta = soup.select_one(selector)
                        if meta:
                            src = meta.get("content", "")
                            if src:
                                news["image"] = src
                                break
                    else:
                        img = soup.select_one(selector)
                        if img:
                            src = img.get("src", "")
                            if src and not src.startswith("http"):
                                src = urljoin(news["link"], src)
                            if src and any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".avif"]):
                                news["image"] = src
                                break

            valid_news.append(news)

        except Exception as e:
            print(f"[详情] 抓取失败 {news['link']}: {e}")
            valid_news.append(news)  # 保留原始新闻，即使详情抓取失败

    return valid_news


# ============================================================
# 主函数
# ============================================================

def fetch_all_news(enabled_categories: List[str] = None) -> List[Dict]:
    """
    抓取所有来源的赛车新闻
    
    Args:
        enabled_categories: 启用的新闻类别列表，None 则表示启用所有
            可选值：F1, NASCAR, MotoGP, WRC, 国内赛车, 中国GT, 澳门格兰披治
    """
    import os
    # 从环境变量读取启用的类别
    if enabled_categories is None:
        cat_str = os.getenv("ENABLED_CATEGORIES", "")
        if cat_str.strip():
            enabled_categories = [c.strip() for c in cat_str.split(",")]
        else:
            enabled_categories = None  # None 表示启用所有

    print("=" * 50)
    print("开始抓取赛车资讯...")
    print(f"抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if enabled_categories:
        print(f"启用类别：{', '.join(enabled_categories)}")
    else:
        print("启用类别：全部")
    print("=" * 50)

    all_news = []

    # 1. F1 新闻（多个源）
    if not enabled_categories or "F1" in enabled_categories:
        print("\n>>> 正在抓取 F1 新闻...")
        f1_news = fetch_f1_rss()
        if not f1_news:
            print("[F1] RSS 源未获取到新闻，尝试网页备份...")
            f1_news = fetch_f1_web_backup()
        all_news.extend(f1_news)

    # 2. NASCAR 新闻
    if not enabled_categories or "NASCAR" in enabled_categories:
        print("\n>>> 正在抓取 NASCAR 新闻...")
        nascar_news = fetch_nascar_news()
        all_news.extend(nascar_news)

    # 3. MotoGP 新闻
    if not enabled_categories or "MotoGP" in enabled_categories:
        print("\n>>> 正在抓取 MotoGP 新闻...")
        motogp_news = fetch_motogp_news()
        all_news.extend(motogp_news)

    # 4. WRC 新闻
    if not enabled_categories or "WRC" in enabled_categories:
        print("\n>>> 正在抓取 WRC 新闻...")
        wrc_news = fetch_wrc_news()
        all_news.extend(wrc_news)

    # 5. 国内赛车新闻
    if not enabled_categories or any(c in enabled_categories for c in ["国内赛车", "中国GT", "澳门格兰披治"]):
        print("\n>>> 正在抓取国内赛车新闻...")
        china_racing_news = fetch_china_racing_news()
        all_news.extend(china_racing_news)

    # 6. 中国 GT / 澳门格兰披治等
    if not enabled_categories or any(c in enabled_categories for c in ["中国GT", "澳门格兰披治", "国内赛事"]):
        print("\n>>> 正在抓取中国 GT / 澳门格兰披治新闻...")
        gt_news = fetch_china_gt_news()
        all_news.extend(gt_news)

    # 去重（根据标题和链接）
    seen = set()
    unique_news = []
    for news in all_news:
        key = (news["title"][:30], news["link"])
        if key not in seen:
            seen.add(key)
            unique_news.append(news)
    all_news = unique_news

    # 7. 补充详情
    if all_news:
        print(f"\n>>> 正在补充 {len(all_news)} 条新闻的详情...")
        all_news = enrich_news_detail(all_news)
    else:
        print("\n[警告] 没有抓取到任何新闻，跳过详情补充")

    # 8. 按时间排序（最新的排最前）
    all_news.sort(key=lambda x: x["pub_time"], reverse=True)

    # 9. 过滤已发布过的新闻（避免和昨天重复）
    published_titles = load_published_history()
    all_news = filter_published_news(all_news, published_titles)

    # 如果过滤后新闻太少，给出提示（不再绕过去重）
    if len(all_news) < 3:
        print(f"\n⚠️  [去重] 过滤后仅剩 {len(all_news)} 条新闻")
        print(f"⚠️  如需更多新闻，请调大 NEWS_MAX_AGE_DAYS 环境变量（当前=2天）")
        print(f"⚠️  但绝不会发布已发布过的新闻！\n")

    # 10. 限制每个类别的新闻条数
    max_per_category = int(os.getenv("MAX_NEWS_PER_CATEGORY", "10"))
    if max_per_category > 0:
        category_count = {}
        filtered_news = []
        for news in all_news:
            cat = news["category"]
            category_count[cat] = category_count.get(cat, 0) + 1
            if category_count[cat] <= max_per_category:
                filtered_news.append(news)
        all_news = filtered_news

    print(f"\n{'=' * 50}")
    print(f"总计抓取到 {len(all_news)} 条有效新闻")
    print(f"{'=' * 50}")

    # 打印分类统计
    categories = {}
    for news in all_news:
        cat = news["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print("\n分类统计：")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 条")

    return all_news


def save_news_to_json(news_list: List[Dict], output_path: str = "data/today_news.json"):
    """保存新闻到 JSON 文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)
    print(f"新闻已保存到：{output_path}")


if __name__ == "__main__":
    news = fetch_all_news()
    save_news_to_json(news)

    # 打印预览
    print("\n--- 新闻预览 ---")
    for i, item in enumerate(news[:5]):
        print(f"\n[{item['category']}] {item['title']}")
        print(f"  来源：{item['source']} | 时间：{item['pub_time'][:10]}")
        print(f"  链接：{item['link']}")
        if item.get('summary'):
            print(f"  摘要：{item['summary'][:80]}...")
