"""
AI 内容处理模块
使用 AI API 对原始新闻进行翻译、摘要、公众号排版
改进：生成完整可编辑内容，过滤广告，优化排版
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
        "temperature": 0.5,
        "max_tokens": 4000,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_ai(messages: list) -> str:
    """统一 AI 调用入口"""
    model = os.getenv("AI_MODEL", "deepseek-chat")
    if model.startswith("deepseek"):
        return call_deepseek(messages, model)
    else:
        return call_deepseek(messages)


# ============================================================
# 新闻内容智能处理
# ============================================================

def process_single_news(news: Dict) -> Dict:
    """处理单条新闻：翻译、提取关键信息、生成完整摘要"""
    title = news.get("title", "")
    summary = news.get("summary", "")
    full_content = news.get("full_content", "")
    lang = news.get("lang", "en")
    category = news.get("category", "F1")
    source = news.get("source", "")
    link = news.get("link", "")

    # 如果 full_content 为空，用 summary 代替
    content = full_content if len(full_content) > 100 else summary
    if not content:
        content = title

    # 根据语言确定 prompt
    if lang == "zh":
        prompt = f"""请阅读以下中文赛车新闻，提取关键信息并生成完整、专业的报道摘要。

【新闻标题】{title}
【来源】{source}
【正文】{content}

请严格按照以下格式输出（不要输出其他内容）：

标题：{title}

摘要：（300-400字，包含比赛结果、关键数据、车手/车队动态、积分榜变化等核心信息，语言专业简洁）

关键词：3-5个关键词，用顿号分隔

原文链接：{link}

注意：
- 摘要必须是完整段落，不能截断
- 必须包含关键数据和比赛结果
- 语言要像专业赛车记者写的
- 不要包含联系方式、公司介绍等无关信息
"""
    else:
        prompt = f"""请阅读以下英文赛车新闻，翻译成中文，并提取关键信息生成完整、专业的报道摘要。

【News Title】{title}
【Source】{source}
【Content】{content}

请严格按照以下格式输出（不要输出其他内容）：

标题：（中文翻译后的标题）

摘要：（300-400字中文，包含比赛结果、关键数据、车手/车队动态、积分榜变化等核心信息，语言专业简洁）

关键词：3-5个中文关键词，用顿号分隔

原文链接：{link}

注意：
- 标题要准确翻译，保留专业术语（如F1、MotoGP等）
- 摘要必须是完整段落，不能截断
- 必须包含关键数据和比赛结果
- 语言要像专业赛车记者写的
- 不要包含联系方式、公司介绍等无关信息
"""

    messages = [
        {"role": "system", "content": "你是一位资深赛车运动记者，精通F1和中国GT赛事报道。你擅长用专业、简洁的语言提炼新闻要点，确保内容完整、信息准确。你从不输出广告内容、联系方式或无关信息。"},
        {"role": "user", "content": prompt}
    ]

    try:
        result = call_ai(messages)

        # 解析 AI 输出
        title_zh = title
        summary_zh = ""
        keywords = ""

        lines = result.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("标题："):
                title_zh = line.replace("标题：", "").strip()
            elif line.startswith("摘要："):
                # 摘要可能跨多行
                summary_lines = [line.replace("摘要：", "").strip()]
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("关键词：") or lines[j].startswith("原文链接："):
                        break
                    summary_lines.append(lines[j].strip())
                summary_zh = " ".join(summary_lines).strip()
            elif line.startswith("关键词："):
                keywords = line.replace("关键词：", "").strip()

        # 如果解析失败，取整段作为摘要
        if not summary_zh and result:
            summary_zh = result.strip()

        # 清理
        summary_zh = summary_zh.replace("(联系方式", "").replace("联系电话", "").replace("传真", "")

        news["title_zh"] = title_zh
        news["summary_zh"] = summary_zh
        news["keywords"] = keywords

        print(f"[AI] 处理完成：{title_zh[:40]}...")

    except Exception as e:
        print(f"[AI] 处理失败 {title}: {e}")
        # 降级处理：直接翻译标题，保留原文摘要
        news["title_zh"] = title if lang == "zh" else title
        news["summary_zh"] = summary[:300] if len(summary) > 10 else title
        news["keywords"] = ""

    return news


# ============================================================
# 生成公众号文章
# ============================================================

def generate_wechat_article(news_list: List[Dict]) -> str:
    """将新闻列表生成为适合公众号编辑的 HTML 内容"""
    today = datetime.now().strftime("%Y年%m月%d日")

    # 按分类分组
    f1_news = [n for n in news_list if n.get("category") == "F1"]
    gt_news = [n for n in news_list if n.get("category") == "中国GT"]

    html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #333; line-height: 1.8; max-width: 100%;">

<!-- 文章头部 -->
<section style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e74c3c; margin-bottom: 20px;">
  <h1 style="font-size: 24px; color: #c0392b; margin: 0 0 8px 0;">🏎️ 赛车日报</h1>
  <p style="font-size: 14px; color: #999; margin: 0;">{today} | F1 & 中国GT世界挑战赛</p>
</section>

"""

    # F1 板块
    if f1_news:
        html += """<section style="margin-bottom: 30px;">
  <h2 style="font-size: 18px; color: #e74c3c; border-left: 4px solid #e74c3c; padding-left: 10px; margin: 0 0 15px 0;">
    🏁 F1 一级方程式
  </h2>
"""

        for i, news in enumerate(f1_news[:5]):
            title = news.get("title_zh") or news.get("title", "")
            summary = news.get("summary_zh") or news.get("summary", "")
            link = news.get("link", "")
            image = news.get("image", "")
            keywords = news.get("keywords", "")
            source = news.get("source", "")

            html += f"""
  <section style="margin-bottom: 25px; padding: 15px; background: #fafafa; border-radius: 8px; border: 1px solid #eee;">
    <h3 style="font-size: 17px; margin: 0 0 10px 0; color: #222; font-weight: bold;">
      {i+1}. {title}
    </h3>
"""
            if image:
                html += f"""    <p style="text-align: center; margin: 10px 0;"><img src="{image}" style="max-width: 100%; border-radius: 6px; display: inline-block;" /></p>
"""

            html += f"""    <p style="font-size: 15px; color: #444; margin: 10px 0; text-align: justify;">{summary}</p>
"""
            if keywords:
                html += f"""    <p style="font-size: 12px; color: #999; margin: 8px 0;">📌 关键词：{keywords}</p>
"""

            html += f"""    <p style="font-size: 12px; color: #999; margin-top: 10px; text-align: right;">
      <span>来源：{source}</span> | <a href="{link}" style="color: #e74c3c; text-decoration: none;">阅读原文 →</a>
    </p>
  </section>
"""

        html += "</section>"

    # 中国 GT 板块
    if gt_news:
        html += """<section style="margin-bottom: 30px;">
  <h2 style="font-size: 18px; color: #2980b9; border-left: 4px solid #2980b9; padding-left: 10px; margin: 0 0 15px 0;">
    🇨🇳 中国GT世界挑战赛
  </h2>
"""

        for i, news in enumerate(gt_news[:5]):
            title = news.get("title_zh") or news.get("title", "")
            summary = news.get("summary_zh") or news.get("summary", "")
            link = news.get("link", "")
            image = news.get("image", "")
            keywords = news.get("keywords", "")
            source = news.get("source", "")

            html += f"""
  <section style="margin-bottom: 25px; padding: 15px; background: #f5f9ff; border-radius: 8px; border: 1px solid #e0eafc;">
    <h3 style="font-size: 17px; margin: 0 0 10px 0; color: #222; font-weight: bold;">
      {i+1}. {title}
    </h3>
"""
            if image:
                html += f"""    <p style="text-align: center; margin: 10px 0;"><img src="{image}" style="max-width: 100%; border-radius: 6px; display: inline-block;" /></p>
"""

            html += f"""    <p style="font-size: 15px; color: #444; margin: 10px 0; text-align: justify;">{summary}</p>
"""
            if keywords:
                html += f"""    <p style="font-size: 12px; color: #999; margin: 8px 0;">📌 关键词：{keywords}</p>
"""

            html += f"""    <p style="font-size: 12px; color: #999; margin-top: 10px; text-align: right;">
      <span>来源：{source}</span> | <a href="{link}" style="color: #2980b9; text-decoration: none;">阅读原文 →</a>
    </p>
  </section>
"""

        html += "</section>"

    # 文章尾部
    html += f"""
<section style="text-align: center; padding: 20px 0; color: #999; font-size: 13px; border-top: 1px solid #eee; margin-top: 20px;">
  <p style="margin: 5px 0;">🏎️ 赛车日报 · 每日 10:00 准时更新</p>
  <p style="margin: 5px 0;">关注我们，第一时间获取 F1 和中国 GT 赛事资讯</p>
  <p style="margin: 5px 0; font-size: 12px; color: #bbb;">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</section>

</div>"""

    return html.strip()


def generate_article_title(news_list: List[Dict]) -> str:
    """生成文章标题"""
    today = datetime.now().strftime("%m月%d日")
    f1_count = len([n for n in news_list if n.get("category") == "F1"])
    gt_count = len([n for n in news_list if n.get("category") == "中国GT"])
    parts = []
    if f1_count > 0:
        parts.append(f"F1动态")
    if gt_count > 0:
        parts.append(f"中国GT")
    return f"🏎️ 赛车日报 | {today}：{'+'.join(parts)} ({len(news_list)}条)"


# ============================================================
# 主函数
# ============================================================

def process_news(news_list: List[Dict]) -> Dict:
    """处理新闻列表，生成公众号文章"""
    print("=" * 50)
    print("开始 AI 处理新闻...")
    print("=" * 50)

    # 过滤掉摘要为空或太短的新闻
    valid_news = [n for n in news_list if (n.get("summary") or n.get("full_content")) and len(n.get("title", "")) > 5]

    if not valid_news:
        print("[AI] 警告：没有有效新闻可处理，生成提示信息...")
        today = datetime.now().strftime("%Y年%m月%d日")
        article_title = f"🏎️ 赛车日报 | {today}（今日暂无新闻）"
        article_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #333; line-height: 1.8; max-width: 100%;">

<section style="text-align: center; padding: 20px 0; border-bottom: 2px solid #e74c3c; margin-bottom: 20px;">
  <h1 style="font-size: 24px; color: #c0392b; margin: 0 0 8px 0;">🏎️ 赛车日报</h1>
  <p style="font-size: 14px; color: #999; margin: 0;">{today} | F1 & 中国GT世界挑战赛</p>
</section>

<section style="margin-bottom: 30px; padding: 20px; background: #fafafa; border-radius: 8px; text-align: center;">
  <p style="font-size: 16px; color: #666; margin: 10px 0;">📢 今日暂无赛车新闻更新</p>
  <p style="font-size: 14px; color: #999; margin: 10px 0;">可能是以下原因：</p>
  <ul style="text-align: left; color: #666; font-size: 14px; line-height: 1.8;">
    <li>新闻源网站暂时无法访问</li>
    <li>最近几天没有重大赛车赛事</li>
    <li>网络连接不稳定</li>
  </ul>
  <p style="font-size: 14px; color: #999; margin: 15px 0;">系统将每天 10:00 自动重试，请耐心等待。</p>
</section>

<section style="text-align: center; padding: 20px 0; color: #999; font-size: 13px; border-top: 1px solid #eee; margin-top: 20px;">
  <p style="margin: 5px 0;">🏎️ 赛车日报 · 每日 10:00 准时更新</p>
  <p style="margin: 5px 0; font-size: 12px; color: #bbb;">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</section>

</div>"""
        result = {
            "title": article_title,
            "content": article_html,
            "news_count": 0,
            "generated_at": datetime.now().isoformat(),
            "news": [],
        }

        # 保存结果
        output_path = "data/processed_article.json"
        os.makedirs("data", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        html_path = "data/preview.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{article_title}</title></head>
<body style="max-width: 680px; margin: 0 auto; padding: 20px;">
{article_html}
</body></html>""")

        return result

    print(f"[AI] 共 {len(valid_news)} 条新闻待处理\n")

    # 对每条新闻进行智能处理
    processed = []
    for i, news in enumerate(valid_news):
        print(f"[AI] 处理第 {i+1}/{len(valid_news)} 条...")
        processed_news = process_single_news(news)
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
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{article_title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
</style>
</head>
<body>
<div class="container">
{article_html}
</div>
</body>
</html>""")

    print(f"预览文件：{html_path}")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = "data/today_news.json"

    with open(input_path, "r", encoding="utf-8") as f:
        news_list = json.load(f)

    result = process_news(news_list)
    print(f"\n完成！共处理 {result['news_count']} 条新闻")
