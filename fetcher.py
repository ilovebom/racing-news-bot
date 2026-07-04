"""
赛车资讯抓取模块
支持 F1（BBC RSS、Motorsport RSS）和中国 GT 世界挑战赛官网
改进：过滤广告、获取完整正文、优化新闻源
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

# 中国GT新闻源配置
CHINA_GT_SOURCES = [
    {
        "name": "ChinaGT官网",
        "url": "http://www.chinagt.net/news/",
        "base": "http://www.chinagt.net",
        "category": "中国GT",
    },
    {
        "name": "新浪赛车",
        "url": "https://sports.sina.com.cn/f1/",
        "base": "https://sports.sina.com.cn",
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
    r'^关于我们', r'^关于\b', r'^首页', r'^\d{3,4}-\d{7,8}',  # 电话号码开头
    r'^联系我们', r'^公司简介',
]


def is_ad_or_spam(title: str, summary: str = "") -> bool:
    """判断是否为广告或垃圾内容"""
    text = title + " " + summary

    # 检查广告关键词
    for kw in AD_KEYWORDS:
        if kw in text:
            return True

    # 检查标题是否以广告模式开头
    for pattern in BAD_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    # 联系方式模式（电话号码等）
    if re.search(r'\d{3,4}-\d{7,8}', text):
        return True

    # 如果正文只有联系方式和简介，没有实质新闻内容
    if len(summary) < 50 and any(kw in summary for kw in ["电话", "邮箱", "地址"]):
        return True

    return False


# ============================================================
# F1 新闻抓取（RSS）
# ============================================================

def fetch_f1_news() -> List[Dict]:
    """抓取 F1 新闻（RSS 源）"""
    all_news = []
    cutoff = datetime.now() - timedelta(hours=48)  # 放宽到48小时，确保有内容

    for source in F1_RSS_SOURCES:
        try:
            print(f"[F1] 正在抓取：{source['name']}")
            feed = feedparser.parse(source["url"])

            for entry in feed.entries[:10]:  # 最多10条
                # 解析发布时间
                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_time = datetime(*entry.updated_parsed[:6])
                else:
                    pub_time = datetime.now()

                # 只保留最近48小时的新闻
                if pub_time < cutoff:
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                # 过滤广告
                if is_ad_or_spam(title, summary):
                    print(f"[F1] 跳过广告：{title[:30]}...")
                    continue

                # 清理 RSS 摘要中的 HTML 标签
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()[:500]

                news = {
                    "title": title,
                    "title_zh": "",
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "pub_time": pub_time.isoformat(),
                    "source": source["name"],
                    "category": source["category"],
                    "lang": source["lang"],
                    "image": "",
                    "full_content": "",  # 待补充完整正文
                }

                # 尝试提取图片
                if hasattr(entry, "media_content") and entry.media_content:
                    news["image"] = entry.media_content[0].get("url", "")
                elif hasattr(entry, "links"):
                    for link in entry.links:
                        if link.get("type", "").startswith("image"):
                            news["image"] = link.get("href", "")
                            break

                all_news.append(news)

        except Exception as e:
            print(f"[F1] 抓取失败 {source['name']}: {e}")

    print(f"[F1] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 中国 GT 新闻抓取
# ============================================================

def fetch_china_gt_from_chinagt() -> List[Dict]:
    """从 ChinaGT 官网抓取新闻"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=7)  # 中国GT新闻更新慢，取7天

    try:
        print("[中国GT] 正在抓取 ChinaGT 官网...")
        url = "http://www.chinagt.net/news/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        # 尝试多种选择器找到新闻列表
        news_items = []
        for selector in [
            ".news-item", ".article-item", "li.news", ".list-item",
            ".news-list li", ".article-list li", ".list li",
            ".items .item", ".newsbox .news",
        ]:
            items = soup.select(selector)
            if items:
                news_items = items
                print(f"[中国GT] 找到 {len(items)} 条新闻（选择器：{selector}）")
                break

        for item in news_items[:8]:
            # 尝试多种方式获取标题和链接
            title = ""
            link = ""

            a_tag = item.select_one("a")
            if a_tag:
                title = a_tag.get_text(strip=True)
                link = a_tag.get("href", "")
            else:
                title_tag = item.select_one("h3, h2, .title, .tit")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    a_in_title = title_tag.select_one("a")
                    if a_in_title:
                        link = a_in_title.get("href", "")

            if not title or len(title) < 5:
                continue

            # 过滤广告
            if is_ad_or_spam(title):
                print(f"[中国GT] 跳过广告：{title[:30]}...")
                continue

            # 处理相对链接
            if link and not link.startswith("http"):
                link = urljoin("http://www.chinagt.net/", link)

            # 获取发布时间
            date_tag = item.select_one(".date, .time, .pubtime, time")
            pub_time = datetime.now()
            if date_tag:
                date_str = date_tag.get_text(strip=True)
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%Y-%m-%d %H:%M"]:
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
            img = item.select_one("img")
            image = img.get("src", "") if img else ""
            if image and not image.startswith("http"):
                image = urljoin("http://www.chinagt.net/", image)

            all_news.append({
                "title": title,
                "title_zh": title,
                "summary": "",
                "link": link,
                "pub_time": pub_time.isoformat(),
                "source": "ChinaGT官网",
                "category": "中国GT",
                "lang": "zh",
                "image": image,
                "full_content": "",
            })

    except Exception as e:
        print(f"[中国GT] ChinaGT官网抓取失败：{e}")

    return all_news


def fetch_china_gt_from_sina() -> List[Dict]:
    """从新浪赛车抓取 F1/GT 相关新闻"""
    all_news = []
    cutoff = datetime.now() - timedelta(days=3)

    try:
        print("[中国GT] 正在抓取新浪赛车...")
        # 新浪赛车 F1 频道
        urls = [
            "https://sports.sina.com.cn/f1/",
        ]
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        for url in urls:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # 新浪的新闻列表通常在特定容器中
            news_items = []
            for selector in [
                "#newslist01 li", "#newslist02 li",
                ".news-list li", ".list-item",
                "ul li a", ".list a",
            ]:
                items = soup.select(selector)
                if items:
                    news_items = items
                    break

            for item in news_items[:8]:
                a_tag = item if item.name == "a" else item.select_one("a")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag.get("href", "")

                if not title or len(title) < 8:
                    continue

                # 过滤非新闻内容
                skip_keywords = ["直播", "视频", "图集", "专题", "排行", "赛程"]
                if any(kw in title for kw in skip_keywords):
                    continue

                # 过滤广告
                if is_ad_or_spam(title):
                    continue

                # 只保留与赛车相关的新闻
                racing_keywords = ["F1", "GT", "赛车", "大奖赛", "排位赛", "正赛", "杆位", "积分", "冠军", "车手", "车队", " Ferrari", "Red Bull", "Mercedes", "迈凯伦", "红牛", "法拉利", "梅奔", "阿隆索", "汉密尔顿", "维斯塔潘"]
                if not any(kw.lower() in title.lower() for kw in racing_keywords):
                    continue

                if link and not link.startswith("http"):
                    link = urljoin("https://sports.sina.com.cn/", link)

                # 获取日期（如果有的话）
                date_tag = item.select_one(".date, .time, span")
                pub_time = datetime.now()
                if date_tag:
                    date_str = date_tag.get_text(strip=True)
                    for fmt in ["%m-%d", "%Y-%m-%d", "%H:%M"]:
                        try:
                            pub_time = datetime.strptime(date_str, fmt)
                            if pub_time.year < 2020:
                                pub_time = pub_time.replace(year=datetime.now().year)
                            break
                        except Exception:
                            continue

                if pub_time < cutoff:
                    continue

                all_news.append({
                    "title": title,
                    "title_zh": title,
                    "summary": "",
                    "link": link,
                    "pub_time": pub_time.isoformat(),
                    "source": "新浪赛车",
                    "category": "中国GT",
                    "lang": "zh",
                    "image": "",
                    "full_content": "",
                })

                if len(all_news) >= 5:
                    break

    except Exception as e:
        print(f"[中国GT] 新浪赛车抓取失败：{e}")

    return all_news


def fetch_china_gt_news() -> List[Dict]:
    """抓取中国 GT 新闻（多源）"""
    all_news = fetch_china_gt_from_chinagt()

    if not all_news:
        all_news = fetch_china_gt_from_sina()

    print(f"[中国GT] 共抓取到 {len(all_news)} 条有效新闻")
    return all_news


# ============================================================
# 新闻详情补充（抓取完整正文）
# ============================================================

def enrich_news_detail(news_list: List[Dict]) -> List[Dict]:
    """补充新闻详情（完整正文、图片）"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for news in news_list:
        if not news.get("link"):
            continue

        try:
            resp = requests.get(news["link"], headers=headers, timeout=10)
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. 提取正文（尽量完整，不截断）
            content_text = ""
            content_selectors = [
                "article", "#article-content", ".article-content",
                ".content", "#content", ".post-content",
                "#news-content", ".news-content", ".detail-content",
                "[class*='content']", "[id*='content']",
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

            # 保存完整内容（用于AI处理）
            news["full_content"] = content_text[:3000]  # 最多3000字，足够AI处理

            # 如果 RSS 没有摘要，从正文生成
            if not news.get("summary"):
                news["summary"] = content_text[:500] if len(content_text) > 50 else ""

            # 2. 提取封面图（如果还没有）
            if not news.get("image"):
                img_selectors = [
                    "article img", ".article-content img", ".content img",
                    "#content img", ".post-content img",
                ]
                for selector in img_selectors:
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

    f1_news = fetch_f1_news()
    gt_news = fetch_china_gt_news()

    all_news = f1_news + gt_news

    # 补充详情（完整正文）
    all_news = enrich_news_detail(all_news)

    # 按时间排序
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
