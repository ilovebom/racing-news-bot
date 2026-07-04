"""
赛车资讯抓取模块
支持 F1（BBC RSS、Motorsport RSS）和中国 GT 世界挑战赛官网
"""

import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict

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

CHINA_GT_URL = "http://www.gt-world-challenge.com.cn/news"
CHINA_GT_NEWS_API = "http://www.gt-world-challenge.com.cn/api/news"  # 尝试 API 接口

# ============================================================
# F1 新闻抓取（RSS）
# ============================================================

def fetch_f1_news() -> List[Dict]:
    """抓取 F1 新闻（RSS 源）"""
    all_news = []
    cutoff = datetime.now() - timedelta(hours=24)  # 只取最近 24 小时

    for source in F1_RSS_SOURCES:
        try:
            print(f"[F1] 正在抓取：{source['name']}")
            feed = feedparser.parse(source["url"])

            for entry in feed.entries:
                # 解析发布时间
                pub_time = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_time = datetime(*entry.updated_parsed[:6])
                else:
                    pub_time = datetime.now()

                # 只保留最近 24 小时的新闻
                if pub_time < cutoff:
                    continue

                news = {
                    "title": entry.get("title", ""),
                    "title_zh": "",  # 待 AI 翻译
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "pub_time": pub_time.isoformat(),
                    "source": source["name"],
                    "category": source["category"],
                    "lang": source["lang"],
                    "image": "",
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

    print(f"[F1] 共抓取到 {len(all_news)} 条新闻")
    return all_news


# ============================================================
# 中国 GT 世界挑战赛新闻抓取
# ============================================================

def fetch_china_gt_news() -> List[Dict]:
    """抓取中国 GT 世界挑战赛新闻"""
    all_news = []
    cutoff = datetime.now() - timedelta(hours=24)

    # 方法 1：尝试抓取官网新闻列表
    try:
        print("[中国GT] 正在抓取官网新闻...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(CHINA_GT_URL, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 解析新闻列表（根据实际网页结构调整选择器）
        news_items = soup.select(".news-item, .article-item, li.news, .list-item")

        for item in news_items[:10]:  # 最多取 10 条
            title_tag = item.select_one("h3, h2, .title, a")
            link_tag = item.select_one("a")
            date_tag = item.select_one(".date, .time, time")
            img_tag = item.select_one("img")

            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            link = link_tag.get("href", "") if link_tag else ""
            if link and not link.startswith("http"):
                link = "http://www.gt-world-challenge.com.cn" + link
            pub_str = date_tag.get_text(strip=True) if date_tag else ""
            image = img_tag.get("src", "") if img_tag else ""
            if image and not image.startswith("http"):
                image = "http://www.gt-world-challenge.com.cn" + image

            # 尝试解析时间
            pub_time = datetime.now()
            if pub_str:
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m-%d %H:%M"]:
                    try:
                        pub_time = datetime.strptime(pub_str, fmt)
                        if pub_time.year < 2020:
                            pub_time = pub_time.replace(year=datetime.now().year)
                        break
                    except Exception:
                        continue

            if pub_time < cutoff:
                continue

            all_news.append({
                "title": title,
                "title_zh": title,  # 中文标题无需翻译
                "summary": "",  # 待抓取详情页补充
                "link": link,
                "pub_time": pub_time.isoformat(),
                "source": "中国GT世界挑战赛官网",
                "category": "中国GT",
                "lang": "zh",
                "image": image,
            })

    except Exception as e:
        print(f"[中国GT] 官网抓取失败：{e}")

    # 方法 2：备用 - 从 Sina 赛车抓取中国 GT 相关新闻
    if not all_news:
        try:
            print("[中国GT] 尝试从新浪赛车抓取...")
            sina_url = "https://sports.sina.com.cn/f1/"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(sina_url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            links = soup.select("a")
            for link_tag in links:
                text = link_tag.get_text(strip=True)
                href = link_tag.get("href", "")
                if ("GT" in text or "世界挑战赛" in text or "中国GT" in text) and href:
                    if not href.startswith("http"):
                        href = "https://sports.sina.com.cn" + href
                    all_news.append({
                        "title": text,
                        "title_zh": text,
                        "summary": "",
                        "link": href,
                        "pub_time": datetime.now().isoformat(),
                        "source": "新浪赛车",
                        "category": "中国GT",
                        "lang": "zh",
                        "image": "",
                    })
                    if len(all_news) >= 5:
                        break
        except Exception as e:
            print(f"[中国GT] 新浪赛车抓取失败：{e}")

    print(f"[中国GT] 共抓取到 {len(all_news)} 条新闻")
    return all_news


# ============================================================
# 新闻详情补充（抓取正文摘要）
# ============================================================

def enrich_news_detail(news_list: List[Dict]) -> List[Dict]:
    """补充新闻详情（正文摘要、图片）"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for news in news_list:
        if news.get("summary"):
            continue  # RSS 已有摘要，跳过
        if not news.get("link"):
            continue

        try:
            resp = requests.get(news["link"], headers=headers, timeout=10)
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, "html.parser")

            # 尝试提取正文
            content_tags = soup.select("p, .content, .article-content, .text")
            summary_parts = []
            for tag in content_tags[:5]:
                text = tag.get_text(strip=True)
                if len(text) > 20:
                    summary_parts.append(text)
            news["summary"] = " ".join(summary_parts)[:300]

            # 尝试提取封面图
            if not news.get("image"):
                img_tags = soup.select("img")
                for img in img_tags:
                    src = img.get("src", "")
                    if src and ("jpg" in src or "png" in src or "jpeg" in src):
                        if not src.startswith("http"):
                            # 相对路径转绝对路径
                            from urllib.parse import urljoin
                            src = urljoin(news["link"], src)
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

    # 补充详情
    all_news = enrich_news_detail(all_news)

    # 按时间排序
    all_news.sort(key=lambda x: x["pub_time"], reverse=True)

    print(f"\n总计抓取到 {len(all_news)} 条新闻")
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
