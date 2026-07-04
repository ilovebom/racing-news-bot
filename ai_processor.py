"""
AI 内容处理模块
使用 AI API 对原始新闻进行翻译、摘要、公众号排版
改进：完善翻译、限制摘要长度≤500字、生成多种格式方便编辑
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
        "temperature": 0.3,  # 降低温度，输出更稳定
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
    """
    处理单条新闻：
    1. 英文新闻翻译成中文
    2. 生成不超过 500 字的摘要
    3. 提取关键词
    """
    title = news.get("title", "")
    summary = news.get("summary", "")
    full_content = news.get("full_content", "")
    lang = news.get("lang", "en")
    category = news.get("category", "F1")
    source = news.get("source", "")
    link = news.get("link", "")
    pub_time = news.get("pub_time", "")[:10]  # 只取日期部分

    # 如果 full_content 为空，用 summary 代替
    content = full_content if len(full_content) > 100 else summary
    if not content:
        content = title

    # 根据语言确定 prompt
    if lang == "zh":
        # 中文新闻：直接生成摘要
        prompt = f"""你是一位资深赛车运动记者。请阅读以下中文赛车新闻，生成一篇专业、简洁的报道摘要。

【新闻标题】{title}
【来源】{source}
【发布时间】{pub_time}
【正文内容】{content[:2000]}

请严格按照以下格式输出（不要输出其他内容）：

标题：{title}

摘要：（中文，不超过 500 字。包含：比赛结果/事件要点、关键数据、车手/车队动态、积分榜变化等核心信息。语言专业简洁，像专业赛车记者写的报道。）

关键词：3-5 个关键词，用顿号分隔（如：F1、墨西哥站、维斯塔潘）

原文链接：{link}

注意：
- 摘要必须完整，不超过 500 字
- 保留专业术语（F1、杆位、领奖台等）
- 不要包含广告、联系方式等无关信息
- 如果内容不足以生成摘要，请根据标题合理推断并标注"据标题整理"
"""
    else:
        # 英文新闻：先翻译，再生成摘要
        prompt = f"""你是一位资深赛车运动记者，精通中英文赛车报道。请阅读以下英文赛车新闻，翻译成中文，并生成专业摘要。

【News Title】{title}
【Source】{source}
【Publish Date】{pub_time}
【Content】{content[:2000]}

请严格按照以下格式输出（不要输出其他内容）：

英文原标题：{title}

标题：（中文翻译后的标题，准确、专业）

摘要：（中文，不超过 500 字。包含：比赛结果/事件要点、关键数据、车手/车队动态、积分榜变化等核心信息。语言专业简洁，像专业赛车记者写的报道。）

关键词：3-5 个中文关键词，用顿号分隔（如：F1、墨西哥站、维斯塔潘）

原文链接：{link}

注意：
- 标题要准确翻译，保留专业术语（F1、Formula 1、pole position、podium 等）
- 摘要必须完整，不超过 500 字
- 如果内容不足以生成摘要，请根据标题合理推断并标注"据标题整理"
- 不要包含广告、联系方式等无关信息
"""

    messages = [
        {"role": "system", "content": "你是一位资深赛车运动记者，精通F1、中国GT、MotoGP等赛事报道。你擅长用专业、简洁的中文提炼新闻要点，确保内容完整、信息准确、语言流畅。你从不输出广告内容、联系方式或无关信息。"},
        {"role": "user", "content": prompt}
    ]

    try:
        result = call_ai(messages)

        # 解析 AI 输出
        title_zh = title
        summary_zh = ""
        keywords = ""
        original_title_en = title if lang != "zh" else ""

        lines = result.strip().split("\n")
        current_field = None
        summary_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("英文原标题：") or line.startswith("英文原标题:"):
                original_title_en = line.replace("英文原标题：", "").replace("英文原标题:", "").strip()
            elif line.startswith("标题：") or line.startswith("标题:"):
                title_zh = line.replace("标题：", "").replace("标题:", "").strip()
                current_field = None
            elif line.startswith("摘要：") or line.startswith("摘要:"):
                summary_lines = [line.replace("摘要：", "").replace("摘要:", "").strip()]
                current_field = "summary"
            elif line.startswith("关键词：") or line.startswith("关键词:"):
                keywords = line.replace("关键词：", "").replace("关键词:", "").strip()
                current_field = None
            elif line.startswith("原文链接：") or line.startswith("原文链接:"):
                current_field = None
            elif current_field == "summary":
                # 摘要多行内容
                if not (line.startswith("关键词") or line.startswith("原文链接")):
                    summary_lines.append(line)

        summary_zh = " ".join(summary_lines).strip()

        # 限制摘要长度不超过 500 字
        if len(summary_zh) > 500:
            summary_zh = summary_zh[:497] + "..."

        # 如果解析失败，取整段作为摘要
        if not summary_zh and result:
            summary_zh = result.strip()[:500]

        # 清理摘要中的广告内容
        ad_patterns = ["电话", "传真", "邮箱", "联系我们", "Copyright", "备案号"]
        for pat in ad_patterns:
            summary_zh = summary_zh.replace(pat, "")

        news["title_zh"] = title_zh
        news["original_title_en"] = original_title_en  # 保存英文原标题
        news["summary_zh"] = summary_zh
        news["keywords"] = keywords
        news["lang"] = lang  # 保留语言标记

        print(f"[AI] 处理完成：{title_zh[:40]}...")

    except Exception as e:
        print(f"[AI] 处理失败 {title}: {e}")
        # 降级处理：保留原文，但添加提示
        news["title_zh"] = title if lang == "zh" else f"[待翻译] {title}"
        news["original_title_en"] = title if lang != "zh" else ""
        
        # 摘要添加失败提示
        if summary and len(summary) > 10:
            fail_msg = f"⚠️ AI 翻译暂不可用（{str(e)[:30]}），以下为原文摘要：\n\n{summary[:500]}"
        else:
            fail_msg = f"⚠️ AI 翻译暂不可用（{str(e)[:30]}），以下为原文标题：\n\n{title}"
        news["summary_zh"] = fail_msg
        news["keywords"] = "AI翻译失败"
        news["translation_failed"] = True  # 标记翻译失败

    return news


# ============================================================
# 生成多种格式的文章内容
# ============================================================

def generate_wechat_html(news_list: List[Dict]) -> str:
    """
    生成适合公众号发布的 HTML 内容
    注意：公众号编辑器对 HTML 支持有限，使用兼容格式
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    article_title = generate_article_title(news_list)

    # 按分类分组
    categorized = {}
    for news in news_list:
        cat = news.get("category", "其他")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(news)

    # 检查是否有翻译失败的新闻
    failed_count = sum(1 for n in news_list if n.get("translation_failed"))
    all_failed = failed_count == len(news_list) and len(news_list) > 0

    # 分类颜色配置
    cat_colors = {
        "F1": {"main": "#e74c3c", "bg": "#fdf2f2", "border": "#fce4e4"},
        "NASCAR": {"main": "#2c3e50", "bg": "#f4f6f7", "border": "#dcdfe3"},
        "MotoGP": {"main": "#f39c12", "bg": "#fef9f3", "border": "#fdebd0"},
        "WRC": {"main": "#27ae60", "bg": "#f0faf4", "border": "#d5f5e3"},
        "中国GT": {"main": "#2980b9", "bg": "#f5f9ff", "border": "#d4e6f9"},
        "澳门格兰披治": {"main": "#8e44ad", "bg": "#f7f0fa", "border": "#e8d5f5"},
        "国内赛车": {"main": "#16a085", "bg": "#e8f8f5", "border": "#d1f2eb"},
    }

    # 文章头部
    html = f"""<!-- 赛车日报 | {today} -->
<!-- 本内容由 AI 自动生成，可直接复制到公众号编辑器 -->

<section style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #333333; line-height: 1.8;">

<!-- 标题区 -->
<section style="text-align: center; padding: 25px 15px; background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); border-radius: 8px; margin-bottom: 25px;">
  <h1 style="font-size: 22px; color: #ffffff; margin: 0 0 8px 0; font-weight: bold; letter-spacing: 1px;">🏎️ 赛车日报</h1>
  <p style="font-size: 14px; color: rgba(255,255,255,0.85); margin: 0;">{today} | 每日 10:00 更新</p>
</section>

"""

    # 如果全部翻译失败，添加醒目的提示
    if all_failed:
        html += f"""
<!-- 翻译失败提示 -->
<section style="margin-bottom: 20px; padding: 15px; background: #fff3cd; border-radius: 8px; border: 1px solid #ffc107; color: #856404;">
  <p style="margin: 0; font-size: 15px; font-weight: bold;">⚠️ AI 翻译服务暂不可用</p>
  <p style="margin: 5px 0 0 0; font-size: 13px; line-height: 1.6;">
    本次内容未经过 AI 翻译，显示为英文原文。请检查 DeepSeek API 余额是否充足，或稍后重试。<br/>
    建议操作：登录 <a href="https://platform.deepseek.com/" style="color: #e74c3c;">DeepSeek 平台</a> 充值 API 余额。
  </p>
</section>
"""
    elif failed_count > 0:
        html += f"""
<!-- 部分翻译失败提示 -->
<section style="margin-bottom: 20px; padding: 12px; background: #fff3cd; border-radius: 8px; border: 1px solid #ffc107; color: #856404;">
  <p style="margin: 0; font-size: 13px;">
    ⚠️ 本次有 {failed_count} 条新闻翻译失败，显示为英文原文。请检查 DeepSeek API 余额。
  </p>
</section>
"""

    # 遍历每个分类
    for cat, items in categorized.items():
        color = cat_colors.get(cat, {"main": "#555555", "bg": "#f9f9f9", "border": "#eeeeee"})

        # 分类标题
        cat_emoji = {
            "F1": "🏁", "NASCAR": "🏎️", "MotoGP": "🏍️",
            "WRC": "🏔️", "中国GT": "🇨🇳", "澳门格兰披治": "🎰", "国内赛车": "🏆"
        }
        emoji = cat_emoji.get(cat, "📌")

        html += f"""
<!-- {cat} 板块 -->
<section style="margin-bottom: 30px;">
  <h2 style="font-size: 18px; color: {color['main']}; border-left: 5px solid {color['main']}; padding-left: 12px; margin: 0 0 18px 0; font-weight: bold;">
    {emoji} {cat}
  </h2>
"""

        # 遍历该分类下的每条新闻
        for i, news in enumerate(items):
            title_zh = news.get("title_zh") or news.get("title", "")
            original_title_en = news.get("original_title_en", "")
            summary_zh = news.get("summary_zh") or news.get("summary", "")
            link = news.get("link", "")
            image = news.get("image", "")
            keywords = news.get("keywords", "")
            source = news.get("source", "")
            pub_date = news.get("pub_time", "")[:10]

            # 每条新闻卡片
            html += f"""
  <section style="margin-bottom: 25px; padding: 18px; background: {color['bg']}; border-radius: 8px; border-left: 3px solid {color['main']};">
"""

            # 英文原标题（如果是外文新闻）
            if original_title_en and original_title_en != title_zh:
                html += f"""    <p style="font-size: 12px; color: #999999; margin: 0 0 6px 0; font-style: italic;">
      🔗 原文标题：{original_title_en}
    </p>
"""

            # 新闻标题
            html += f"""    <h3 style="font-size: 16px; margin: 0 0 10px 0; color: #222222; font-weight: bold; line-height: 1.5;">
      {i+1}. {title_zh}
    </h3>
"""

            # 封面图
            if image:
                html += f"""    <p style="text-align: center; margin: 10px 0;">
      <img src="{image}" style="max-width: 100%; height: auto; border-radius: 6px;" />
    </p>
"""

            # 摘要正文
            html += f"""    <p style="font-size: 14px; color: #444444; margin: 10px 0; text-align: justify; line-height: 1.8;">
      {summary_zh}
    </p>
"""

            # 关键词
            if keywords:
                html += f"""    <p style="font-size: 12px; color: #888888; margin: 8px 0;">
      📌 关键词：{keywords}
    </p>
"""

            # 来源和时间
            meta_parts = []
            if source:
                meta_parts.append(f"来源：{source}")
            if pub_date:
                meta_parts.append(f"日期：{pub_date}")
            if meta_parts:
                html += f"""    <p style="font-size: 12px; color: #999999; margin: 8px 0; text-align: right;">
      {' | '.join(meta_parts)}
    </p>
"""

            # 原文链接
            if link:
                html += f"""    <p style="font-size: 12px; margin: 8px 0; text-align: right;">
      <a href="{link}" style="color: {color['main']}; text-decoration: none;">📎 查看原文 →</a>
    </p>
"""

            html += "  </section>\n"

        html += "</section>\n"

    # 文章尾部
    html += f"""
<!-- 文章尾部 -->
<section style="text-align: center; padding: 20px 15px; background: #f8f8f8; border-radius: 8px; margin-top: 30px; color: #999999; font-size: 13px;">
  <p style="margin: 5px 0;">🏎️ 赛车日报 · 每日 10:00 准时更新</p>
  <p style="margin: 5px 0;">关注我们，第一时间获取 F1、中国GT 等赛事资讯</p>
  <p style="margin: 5px 0; font-size: 12px; color: #bbbbbb;">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</section>

</section>
"""

    return html.strip()


def generate_plain_text(news_list: List[Dict]) -> str:
    """
    生成纯文本格式，方便直接复制粘贴到公众号编辑器
    纯文本格式最兼容，编辑时可以自行加粗、添加图片
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    article_title = generate_article_title(news_list)

    lines = []
    lines.append("=" * 40)
    lines.append(f"🏎️ 赛车日报 | {today}")
    lines.append("=" * 40)
    lines.append("")

    # 检查是否有翻译失败
    failed_count = sum(1 for n in news_list if n.get("translation_failed"))
    all_failed = failed_count == len(news_list) and len(news_list) > 0

    if all_failed:
        lines.append("⚠️【提示】AI 翻译服务暂不可用")
        lines.append("   本次内容显示为英文原文，请检查 DeepSeek API 余额是否充足。")
        lines.append("   建议：登录 https://platform.deepseek.com/ 充值 API 余额")
        lines.append("")
    elif failed_count > 0:
        lines.append(f"⚠️【提示】本次有 {failed_count} 条新闻翻译失败，显示为英文原文")
        lines.append("")

    # 按分类分组
    categorized = {}
    for news in news_list:
        cat = news.get("category", "其他")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(news)

    cat_emoji = {
        "F1": "🏁", "NASCAR": "🏎️", "MotoGP": "🏍️",
        "WRC": "🏔️", "中国GT": "🇨🇳", "澳门格兰披治": "🎰", "国内赛车": "🏆"
    }

    for cat, items in categorized.items():
        emoji = cat_emoji.get(cat, "📌")
        lines.append(f"{emoji} {cat}")
        lines.append("-" * 40)

        for i, news in enumerate(items):
            title_zh = news.get("title_zh") or news.get("title", "")
            original_title_en = news.get("original_title_en", "")
            summary_zh = news.get("summary_zh") or news.get("summary", "")
            keywords = news.get("keywords", "")
            source = news.get("source", "")
            pub_date = news.get("pub_time", "")[:10]
            link = news.get("link", "")

            lines.append("")
            lines.append(f"【{i+1}】{title_zh}")
            lines.append("")

            # 英文原标题
            if original_title_en and original_title_en != title_zh:
                lines.append(f"🔗 原文标题：{original_title_en}")
                lines.append("")

            # 摘要
            lines.append(summary_zh)
            lines.append("")

            # 关键词
            if keywords:
                lines.append(f"📌 关键词：{keywords}")

            # 来源
            meta_parts = []
            if source:
                meta_parts.append(f"来源：{source}")
            if pub_date:
                meta_parts.append(f"日期：{pub_date}")
            if meta_parts:
                lines.append(" | ".join(meta_parts))

            # 原文链接
            if link:
                lines.append(f"📎 原文：{link}")

            lines.append("")
            lines.append("-" * 40)

        lines.append("")

    lines.append("=" * 40)
    lines.append("🏎️ 赛车日报 · 每日 10:00 准时更新")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 40)

    return "\n".join(lines)


def generate_markdown(news_list: List[Dict]) -> str:
    """生成 Markdown 格式，方便在其他平台发布"""
    today = datetime.now().strftime("%Y年%m月%d日")

    md_lines = []
    md_lines.append(f"# 🏎️ 赛车日报 | {today}")
    md_lines.append("")
    md_lines.append("> 每日 10:00 自动更新，汇总全球赛车资讯")
    md_lines.append("")

    # 按分类分组
    categorized = {}
    for news in news_list:
        cat = news.get("category", "其他")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(news)

    cat_emoji = {
        "F1": "🏁", "NASCAR": "🏎️", "MotoGP": "🏍️",
        "WRC": "🏔️", "中国GT": "🇨🇳", "澳门格兰披治": "🎰", "国内赛车": "🏆"
    }

    for cat, items in categorized.items():
        emoji = cat_emoji.get(cat, "📌")
        md_lines.append(f"## {emoji} {cat}")
        md_lines.append("")

        for i, news in enumerate(items):
            title_zh = news.get("title_zh") or news.get("title", "")
            original_title_en = news.get("original_title_en", "")
            summary_zh = news.get("summary_zh") or news.get("summary", "")
            keywords = news.get("keywords", "")
            source = news.get("source", "")
            pub_date = news.get("pub_time", "")[:10]
            link = news.get("link", "")
            image = news.get("image", "")

            md_lines.append(f"### {i+1}. {title_zh}")
            md_lines.append("")

            if original_title_en and original_title_en != title_zh:
                md_lines.append(f"> 🔗 原文标题：{original_title_en}")
                md_lines.append("")

            if image:
                md_lines.append(f"![{title_zh}]({image})")
                md_lines.append("")

            md_lines.append(summary_zh)
            md_lines.append("")

            if keywords:
                md_lines.append(f"**关键词**：{keywords}")
                md_lines.append("")

            meta_parts = []
            if source:
                meta_parts.append(f"来源：{source}")
            if pub_date:
                meta_parts.append(f"日期：{pub_date}")
            if meta_parts:
                md_lines.append(f"*{ ' | '.join(meta_parts) }*")
                md_lines.append("")

            if link:
                md_lines.append(f"[📎 查看原文]({link})")
                md_lines.append("")

            md_lines.append("---")
            md_lines.append("")

    md_lines.append(f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    md_lines.append("")
    md_lines.append("#赛车日报 #F1 #中国GT")

    return "\n".join(md_lines)


def generate_article_title(news_list: List[Dict]) -> str:
    """生成文章标题"""
    today = datetime.now().strftime("%m月%d日")
    cat_count = {}
    for news in news_list:
        cat = news.get("category", "其他")
        cat_count[cat] = cat_count.get(cat, 0) + 1

    parts = []
    if cat_count.get("F1", 0) > 0:
        parts.append("F1动态")
    if any(c in cat_count for c in ["中国GT", "澳门格兰披治", "国内赛车"]):
        parts.append("国内赛事")
    if cat_count.get("NASCAR", 0) > 0:
        parts.append("NASCAR")
    if cat_count.get("MotoGP", 0) > 0:
        parts.append("MotoGP")

    return f"🏎️ 赛车日报 | {today}：{'+'.join(parts)}（共{len(news_list)}条）"


# ============================================================
# 主函数
# ============================================================

def process_news(news_list: List[Dict]) -> Dict:
    """处理新闻列表，生成多种格式的文章内容"""
    print("=" * 50)
    print("开始 AI 处理新闻...")
    print(f"待处理新闻数：{len(news_list)}")
    print("=" * 50)

    # 过滤掉摘要为空或太短的新闻
    valid_news = [n for n in news_list
                   if (n.get("summary") or n.get("full_content")) and len(n.get("title", "")) > 5]

    if not valid_news:
        print("[AI] 警告：没有有效新闻可处理，生成提示信息...")
        today = datetime.now().strftime("%Y年%m月%d日")
        article_title = f"🏎️ 赛车日报 | {today}（今日暂无新闻）"
        article_html = generate_no_news_html(today)
        result = {
            "title": article_title,
            "content": article_html,
            "plain_text": generate_no_news_plain(today),
            "markdown": generate_no_news_md(today),
            "news_count": 0,
            "generated_at": datetime.now().isoformat(),
            "news": [],
        }
        save_result(result)
        return result

    print(f"[AI] 共 {len(valid_news)} 条新闻待处理\n")

    # 对每条新闻进行智能处理
    processed = []
    for i, news in enumerate(valid_news):
        print(f"[AI] 处理第 {i+1}/{len(valid_news)} 条：{news.get('title', '')[:40]}...")
        processed_news = process_single_news(news)
        processed.append(processed_news)

    # 按分类排序
    cat_order = {"F1": 0, "NASCAR": 1, "MotoGP": 2, "WRC": 3, "中国GT": 4, "澳门格兰披治": 5, "国内赛车": 6}
    processed.sort(key=lambda x: cat_order.get(x.get("category", ""), 99))

    # 生成多种格式
    print("\n[AI] 生成文章内容...")
    article_html = generate_wechat_html(processed)
    article_plain = generate_plain_text(processed)
    article_md = generate_markdown(processed)
    article_title = generate_article_title(processed)

    result = {
        "title": article_title,
        "content": article_html,
        "plain_text": article_plain,
        "markdown": article_md,
        "news_count": len(processed),
        "generated_at": datetime.now().isoformat(),
        "news": processed,
    }

    # 保存结果
    save_result(result)

    print(f"\n{'=' * 50}")
    print(f"✅ 文章生成完成！")
    print(f"  标题：{article_title}")
    print(f"  新闻条数：{len(processed)}")
    print(f"  输出文件：")
    print(f"    - data/processed_article.json（完整数据）")
    print(f"    - data/preview.html（公众号 HTML 预览）")
    print(f"    - data/article_plain.txt（纯文本，推荐复制使用）")
    print(f"    - data/article.md（Markdown 格式）")
    print(f"{'=' * 50}")

    return result


def save_result(result: Dict):
    """保存处理结果到多个文件"""
    os.makedirs("data", exist_ok=True)

    # 1. 保存完整 JSON 数据
    json_path = "data/processed_article.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[保存] {json_path}")

    # 2. 保存公众号 HTML（预览用）
    html_path = "data/preview.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{result['title']}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
h1, h2, h3 {{ margin-top: 0; }}
</style>
</head>
<body>
<div class="container">
{result['content']}
</div>
</body>
</html>""")
    print(f"[保存] {html_path}")

    # 3. 保存纯文本版本（推荐用于复制粘贴到公众号）
    plain_path = "data/article_plain.txt"
    with open(plain_path, "w", encoding="utf-8") as f:
        f.write(result.get("plain_text", ""))
    print(f"[保存] {plain_path}")

    # 4. 保存 Markdown 版本
    md_path = "data/article.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result.get("markdown", ""))
    print(f"[保存] {md_path}")


def generate_no_news_html(today: str) -> str:
    """生成暂无新闻的 HTML"""
    return f"""<section style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #333; line-height: 1.8;">
<section style="text-align: center; padding: 25px 15px; background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); border-radius: 8px; margin-bottom: 25px;">
  <h1 style="font-size: 22px; color: #ffffff; margin: 0 0 8px 0; font-weight: bold;">🏎️ 赛车日报</h1>
  <p style="font-size: 14px; color: rgba(255,255,255,0.85); margin: 0;">{today}</p>
</section>
<section style="margin-bottom: 30px; padding: 20px; background: #fafafa; border-radius: 8px; text-align: center;">
  <p style="font-size: 16px; color: #666; margin: 10px 0;">📭 今日暂无赛车新闻更新</p>
  <p style="font-size: 14px; color: #999; margin: 10px 0;">可能是以下原因：</p>
  <ul style="text-align: left; color: #666; font-size: 14px; line-height: 1.8; max-width: 400px; margin: 0 auto;">
    <li>新闻源网站暂时无法访问</li>
    <li>最近几天没有重大赛车赛事</li>
    <li>网络连接不稳定</li>
  </ul>
  <p style="font-size: 14px; color: #999; margin: 15px 0;">系统将每天 10:00 自动重试，请耐心等待。</p>
</section>
<section style="text-align: center; padding: 20px 15px; background: #f8f8f8; border-radius: 8px; margin-top: 30px; color: #999; font-size: 13px;">
  <p style="margin: 5px 0;">🏎️ 赛车日报 · 每日 10:00 准时更新</p>
  <p style="margin: 5px 0; font-size: 12px; color: #bbb;">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</section>
</section>"""


def generate_no_news_plain(today: str) -> str:
    """生成暂无新闻的纯文本"""
    return f"""========================================
🏎️ 赛车日报 | {today}
========================================

📭 今日暂无赛车新闻更新

可能是以下原因：
- 新闻源网站暂时无法访问
- 最近几天没有重大赛车赛事
- 网络连接不稳定

系统将每天 10:00 自动重试，请耐心等待。

========================================
🏎️ 赛车日报 · 每日 10:00 准时更新
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
========================================
"""


def generate_no_news_md(today: str) -> str:
    """生成暂无新闻的 Markdown"""
    return f"""# 🏎️ 赛车日报 | {today}

> 每日 10:00 自动更新，汇总全球赛车资讯

## 📭 今日暂无赛车新闻更新

可能是以下原因：
- 新闻源网站暂时无法访问
- 最近几天没有重大赛车赛事
- 网络连接不稳定

系统将每天 10:00 自动重试，请耐心等待。

---

*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""


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
