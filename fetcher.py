"""
赛车资讯抓取模块
支持 F1（BBC RSS、Motorsport RSS、网页抓取）和中国GT新闻
改进：多源冗余、自动过滤广告、获取完整正文、网络错误降级
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
]

# F1 网页备份源
F1_WEB_SOURCES = [
    {
        "name": "BBC Sport F1 网页",
        "url": "https://www.bbc.com/sport/formula1",
        "category": "F1",
    },
    {
        "name": "Motorsport 网页",
        "url": "https://www.motorsport.com/f1/",
        "category": "F1",
    },
]

# 中国GT新闻源
CHINA_GT_SOURCES = [
    {
        "name": "ChinaGT官网",
        "url": "http://www.chinagt.net/news/",
        "category": "中国GT",
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
]

BAD_TITLE_PATTERNS = [
    r'^电话', r'^传真', r'^邮箱', r'^地址', r'^联系',
    r'^关于我们', r'^关于\b', r'^首页', r'^\d{3,4}-\d{7,8}',
    r'^联系我们', r'^公司简介',
]


def is_ad_or_spam(title: str, summary: str = "") -> bool:
    """判断是否为广告或垃圾内容"""
    text = title + " " + summary

    for kw in AD_KEYWORDS:
        if kw in text:
            return True

    for pattern in BAD_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    if re.search(r'\d{3,4}-\d{7,8}', text):
        return True

    if len(summary) < 50 and any(kw in summary for kw in ["电话", "邮箱", "地址"]):
        return True

    return False


# ============================================================
# F1 新闻抓取（RSS）
# ============================================================

def fetch_f1_rss() -> List[Dict]:
    """从 RSS 源抓取 F1 新闻"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=7)  # 放宽到7天

    for source in F1_RSS_SOURCES:
        try:
            print(f"[F1 RSS] 正在抓取：{source['name']}")
            feed = feedparser.parse(source["url"])

            # 检查 RSS 是否成功解析
            if not feed.entries:
                print(f"[F1 RSS] 警告：{source['name']} 没有返回条目")
                continue

            print(f"[F1 RSS] {source['name']} 返回 {len(feed.entries)} 条原始条目")

            for entry in feed.entries[:15]:
                # 解析发布时间
                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub_time = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    try:
                        pub_time = datetime(*entry.updated_parsed[:6])
                    except Exception:
                        pass

                if not pub_time:
                    pub_time = datetime.now() - timedelta(days=1)  # 默认昨天

                # 只保留最近7天的新闻
                if pub_time < cutoff:
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                # 清理 RSS 摘要中的 HTML 标签
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()

                # 过滤广告
                if is_ad_or_spam(title, summary):
                    print(f"[F1 RSS] 跳过广告：{title[:30]}...")
                    continue

                # 过滤空标题
                if len(title) < 5:
                    continue

                # 过滤非赛车内容（BBC Sport RSS 有时会包含其他体育新闻）
                racing_keywords = ["f1", "formula 1", "formula one", "grand prix", " qualifying", "race", "prix", "车手", "车队", "ferrari", "red bull", "mercedes", "mclaren", "verstappen", "hamilton", "leclerc", "norris"]
                title_lower = title.lower()
                if not any(kw in title_lower for kw in racing_keywords):
                    print(f"[F1 RSS] 跳过非赛车新闻：{title[:40]}...")
                    continue

                news = {
                    "title": title,
                    "title_zh": "",
                    "summary": summary[:500],
                    "link": entry.get("link", ""),
                    "pub_time": pub_time.isoformat(),
                    "source": source["name"],
                    "category": source["category"],
                    "lang": source["lang"],
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
                # 尝试从 enclosure 提取图片
                if not news["image"] and hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image"):
                            news["image"] = enc.get("href", "")
                            break

                all_news.append(news)
                print(f"[F1 RSS] ✓ 抓取到：{title[:50]}...")

        except Exception as e:
            print(f"[F1 RSS] 抓取失败 {source['name']}: {e}")

    print(f"[F1 RSS] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# F1 新闻抓取（网页备份）
# ============================================================

def fetch_f1_web_backup() -> List[Dict]:
    """从网页抓取 F1 新闻作为备份"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=7)

    for source in F1_WEB_SOURCES:
        try:
            print(f"[F1 Web] 正在抓取：{source['name']}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(source["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, "html.parser")

            # 根据来源选择不同的解析策略
            articles = []
            if "bbc" in source["url"]:
                # BBC Sport 文章列表
                articles = soup.select("[data-testid='card-headline']")
                if not articles:
                    articles = soup.select("h3")
            elif "motorsport" in source["url"]:
                # Motorsport 文章列表
                articles = soup.select("article a, .news-item a, .article-title a")
                if not articles:
                    articles = soup.select("h3 a, h2 a")

            for article in articles[:10]:
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

                # 过滤非赛车内容
                racing_keywords = ["f1", "formula", "grand prix", "race", "qualifying", "prix", "verstappen", "hamilton", "leclerc", "norris", "perez", "russell"]
                if not any(kw in title.lower() for kw in racing_keywords):
                    continue

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
                    "category": "F1",
                    "lang": "en",
                    "image": "",
                    "full_content": "",
                })
                print(f"[F1 Web] ✓ 抓取到：{title[:50]}...")

                if len(all_news) >= 5:
                    break

        except Exception as e:
            print(f"[F1 Web] 抓取失败 {source['name']}: {e}")

    print(f"[F1 Web] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 中国 GT 新闻抓取
# ============================================================

def fetch_china_gt_news() -> List[Dict]:
    """抓取中国 GT 新闻"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=30)  # 中国GT新闻更新慢，放宽到30天

    for source in CHINA_GT_SOURCES:
        try:
            print(f"[中国GT] 正在抓取：{source['name']}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            resp = requests.get(source["url"], headers=headers, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            print(f"[中国GT] 页面标题：{soup.title.string if soup.title else 'N/A'}")
            print(f"[中国GT] 页面大小：{len(resp.text)} 字符")

            # 尝试多种选择器找到新闻列表
            news_items = []
            selectors = [
                ".news-item", ".article-item", "li.news", ".list-item",
                ".news-list li", ".article-list li", ".list li",
                ".items .item", ".newsbox .news", ".news li",
                "article", ".post", ".entry",
            ]
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    news_items = items
                    print(f"[中国GT] 找到 {len(items)} 条新闻（选择器：{selector}）")
                    break

            # 如果没找到，尝试直接找所有包含链接的元素
            if not news_items:
                all_links = soup.select("a")
                for link in all_links:
                    text = link.get_text(strip=True)
                    if len(text) > 10 and len(text) < 100 and any(kw in text for kw in ["GT", "赛车", "比赛", "站", "冠军", "车队", "车手"]):
                        news_items.append(link)
                if news_items:
                    print(f"[中国GT] 通过文本匹配找到 {len(news_items)} 条新闻")

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
                    print(f"[中国GT] 跳过广告：{title[:30]}...")
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
                    "category": "中国GT",
                    "lang": "zh",
                    "image": image,
                    "full_content": "",
                })
                print(f"[中国GT] ✓ 抓取到：{title[:50]}...")

                if len(all_news) >= 8:
                    break

        except Exception as e:
            print(f"[中国GT] 抓取失败 {source['name']}: {e}")

    print(f"[中国GT] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 新闻详情补充（抓取完整正文）
# ============================================================

def enrich_news_detail(news_list: List[Dict]) -> List[Dict]:
    """补充新闻详情（完整正文、图片）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for news in news_list:
        if not news.get("link"):
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

            # 保存完整内容
            news["full_content"] = content_text[:3000]

            # 如果 RSS 没有摘要，从正文生成
            if not news.get("summary") or len(news.get("summary", "")) < 50:
                news["summary"] = content_text[:500] if len(content_text) > 50 else ""

            # 2. 提取封面图
            if not news.get("image"):
                img_selectors = [
                    "article img", ".article-content img", ".content img",
                    "#content img", ".post-content img", "meta[property='og:image']",
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
                            if src and any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                                news["image"] = src
                                break

        except Exception as e:
            print(f"[详情] 抓取失败 {news['link']}: {e}")

    return news_list


# ============================================================
# 主函数
# ============================================================

def fetch_all_news() -> List[Dict]:
    """抓取所有来源的赛车新闻"""
    print("=" * 50)
    print("开始抓取赛车资讯...")
    print(f"抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 1. 尝试 RSS 源
    f1_news = fetch_f1_rss()

    # 2. 如果 RSS 失败，尝试网页备份
    if not f1_news:
        print("[F1] RSS 源未获取到新闻，尝试网页备份...")
        f1_news = fetch_f1_web_backup()

    # 3. 抓取中国GT
    gt_news = fetch_china_gt_news()

    all_news = f1_news + gt_news

    # 4. 补充详情
    if all_news:
        all_news = enrich_news_detail(all_news)
    else:
        print("\n[警告] 没有抓取到任何新闻，跳过详情补充")

    # 5. 按时间排序
    all_news.sort(key=lambda x: x["pub_time"], reverse=True)

    print(f"\n总计抓取到 {len(all_news)} 条有效新闻")
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
