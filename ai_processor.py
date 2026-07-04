"""
AI 内容处理模块
使用 AI API 对原始新闻进行翻译、摘要、公众号排版
支持 DeepSeek API 和通义千问 API
"""

import os
import json
import requests
from typing import List, Dict
from datetime import datetime


# ============================================================
# AI API 调用封装
# ============================================================

def call_deepseek(messages: list, model: str = "deepseek-chat") -> str:
    """调用 DeepSeek API"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未设置 DEEPSEEK_API_KEY 环境变量")

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_qwen(messages: list, model: str = "qwen-turbo") -> str:
    """调用通义千问 API（DashScope）"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未设置 DASHSCOPE_API_KEY 环境变量")

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # 转换 messages 格式
    payload = {
        "model": model,
        "input": {
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages]
        },
        "parameters": {"temperature": 0.3, "max_tokens": 2000}
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["output"]["text"]


def call_ai(messages: list) -> str:
    """统一 AI 调用入口"""
    model = os.getenv("AI_MODEL", "deepseek-chat")
    if model.startswith("deepseek"):
        return call_deepseek(messages, model)
    elif model.startswith("qwen"):
        return call_qwen(messages, model)
    else:
        return call_deepseek(messages)


# ============================================================
# 新闻翻译 & 摘要
# ============================================================

def translate_and_summarize(news: Dict) -> Dict:
    """翻译并摘要单条新闻"""
    if news.get("lang") == "zh" and news.get("summary"):
        # 中文新闻，直接生成摘要
        prompt = f"""
请对以下中文赛车新闻进行摘要，控制在 150 字以内，保留关键信息（比赛结果、车手动态、积分变化等）。

标题：{news['title']}
正文：{news.get('summary', '')}

输出格式：
标题：（保持原标题）
摘要：（150字以内的精华摘要）
"""
    else:
        # 英文新闻，需要翻译+摘要
        prompt = f"""
请将以下英文 F1 赛车新闻翻译成中文，并生成 150 字以内的摘要。

英文标题：{news['title']}
英文正文：{news.get('summary', news.get('title', ''))}

输出格式（严格按此格式）：
标题：（中文翻译后的标题）
摘要：（150字以内的中文精华摘要，保留关键信息）
"""

    messages = [
        {"role": "system", "content": "你是一位专业的赛车运动记者，擅长 F1 和中国 GT 赛事报道，文字简洁专业。"},
        {"role": "user", "content": prompt}
    ]

    try:
        result = call_ai(messages)
        # 解析结果
        lines = result.strip().split("\n")
        title_zh = news.get("title", "")
        summary_zh = ""

        for line in lines:
            if line.startswith("标题："):
                title_zh = line.replace("标题：", "").strip()
            elif line.startswith("摘要："):
                summary_zh = line.replace("摘要：", "").strip()

        if not summary_zh:
            # 如果解析失败，取最后一段作为摘要
            summary_zh = result.strip().split("\n")[-1][:200]

        news["title_zh"] = title_zh
        news["summary_zh"] = summary_zh
        print(f"[AI] 处理完成：{title_zh[:30]}...")

    except Exception as e:
        print(f"[AI] 处理失败 {news['title']}: {e}")
        news["title_zh"] = news.get("title", "")
        news["summary_zh"] = news.get("summary", "")[:150]

    return news


# ============================================================
# 生成公众号文章
# ============================================================

def generate_wechat_article(news_list: List[Dict]) -> str:
    """将新闻列表生成为公众号文章 HTML"""
    today = datetime.now().strftime("%Y年%m月%d日")

    # 按分类分组
    f1_news = [n for n in news_list if n.get("category") == "F1"]
    gt_news = [n for n in news_list if n.get("category") == "中国GT"]

    html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #333; line-height: 1.8;">

<!-- 文章头部 -->
<section style="text-align: center; padding: 20px 0;">
  <h1 style="font-size: 22px; color: #c0392b; margin-bottom: 8px;">🏎️ 赛车日报</h1>
  <p style="font-size: 14px; color: #999;">{today} | F1 & 中国GT世界挑战赛</p>
  <hr style="border: none; border-top: 2px solid #c0392b; width: 60px; margin: 15px auto;">
</section>

<!-- F1 板块 -->
"""

    if f1_news:
        html += """
<section style="margin-bottom: 30px;">
  <h2 style="font-size: 18px; color: #e74c3c; border-left: 4px solid #e74c3c; padding-left: 10px; margin-bottom: 15px;">
    🏁 F1 一级方程式
  </h2>
"""

        for i, news in enumerate(f1_news[:5]):  # 最多 5 条 F1 新闻
            title = news.get("title_zh") or news.get("title", "")
            summary = news.get("summary_zh") or news.get("summary", "")
            link = news.get("link", "")
            image = news.get("image", "")

            html += f"""
  <section style="margin-bottom: 20px; padding: 15px; background: #f9f9f9; border-radius: 8px;">
    <h3 style="font-size: 16px; margin: 0 0 8px 0; color: #222;">
      <a href="{link}" style="color: #222; text-decoration: none;">{i+1}. {title}</a>
    </h3>
"""
            if image:
                html += f"""    <p style="text-align: center; margin: 10px 0;"><img src="{image}" style="max-width: 100%; border-radius: 6px;" /></p>
"""
            html += f"""
    <p style="font-size: 14px; color: #555; margin: 8px 0;">{summary}</p>
    <p style="font-size: 12px; color: #999; text-align: right;">
      <a href="{link}" style="color: #e74c3c; text-decoration: none;">阅读原文 →</a>
    </p>
  </section>
"""

        html += "</section>"

    # 中国 GT 板块
    if gt_news:
        html += """
<section style="margin-bottom: 30px;">
  <h2 style="font-size: 18px; color: #2980b9; border-left: 4px solid #2980b9; padding-left: 10px; margin-bottom: 15px;">
    🇨🇳 中国GT世界挑战赛
  </h2>
"""

        for i, news in enumerate(gt_news[:5]):
            title = news.get("title_zh") or news.get("title", "")
            summary = news.get("summary_zh") or news.get("summary", "")
            link = news.get("link", "")
            image = news.get("image", "")

            html += f"""
  <section style="margin-bottom: 20px; padding: 15px; background: #f0f7ff; border-radius: 8px;">
    <h3 style="font-size: 16px; margin: 0 0 8px 0; color: #222;">
      <a href="{link}" style="color: #222; text-decoration: none;">{i+1}. {title}</a>
    </h3>
"""
            if image:
                html += f"""    <p style="text-align: center; margin: 10px 0;"><img src="{image}" style="max-width: 100%; border-radius: 6px;" /></p>
"""
            html += f"""
    <p style="font-size: 14px; color: #555; margin: 8px 0;">{summary}</p>
    <p style="font-size: 12px; color: #999; text-align: right;">
      <a href="{link}" style="color: #2980b9; text-decoration: none;">阅读原文 →</a>
    </p>
  </section>
"""

        html += "</section>"

    # 文章尾部
    html += """
<section style="text-align: center; padding: 20px 0; color: #999; font-size: 13px;">
  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p>🏎️ 赛车日报 · 每日 10:00 准时更新</p>
  <p>关注我们，第一时间获取 F1 和中国 GT 赛事资讯</p>
</section>

</div>
"""

    return html.strip()


def generate_article_title(news_list: List[Dict]) -> str:
    """生成文章标题"""
    today = datetime.now().strftime("%m月%d日")
    f1_count = len([n for n in news_list if n.get("category") == "F1"])
    gt_count = len([n for n in news_list if n.get("category") == "中国GT"])
    return f"🏎️ 赛车日报 | {today}：F1最新动态 + 中国GT赛事（共{len(news_list)}条）"


# ============================================================
# 主函数
# ============================================================

def process_news(news_list: List[Dict]) -> Dict:
    """处理新闻列表，生成公众号文章"""
    print("=" * 50)
    print("开始 AI 处理新闻...")
    print("=" * 50)

    # 对每条新闻进行翻译/摘要
    processed = []
    for news in news_list:
        processed_news = translate_and_summarize(news)
        processed.append(processed_news)

    # 生成公众号文章
    article_html = generate_wechat_article(processed)
    article_title = generate_article_title(processed)

    result = {
        "title": article_title,
        "content": article_html,
        "news_count": len(processed),
        "generated_at": datetime.now().isoformat(),
        "news": processed,
    }

    # 保存结果
    output_path = "data/processed_article.json"
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n文章已生成：{article_title}")
    print(f"内容已保存到：{output_path}")

    # 同时保存为 HTML（方便预览）
    html_path = "data/preview.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{article_title}</title></head>
<body style="max-width: 680px; margin: 0 auto; padding: 20px;">
{article_html}
</body></html>""")

    print(f"预览文件：{html_path}")
    return result


if __name__ == "__main__":
    # 测试：加载已抓取的新闻，进行处理
    import sys
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "data/today_news.json"

    with open(input_path, "r", encoding="utf-8") as f:
        news_list = json.load(f)

    result = process_news(news_list)
    print(f"\n完成！共处理 {result['news_count']} 条新闻")
