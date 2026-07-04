"""
主程序入口
串联新闻抓取 → AI 处理 → 自动发布 全流程
"""

import os
import sys
import json
from datetime import datetime

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("[主程序] 提示：未安装 python-dotenv，将使用系统环境变量")


def main():
    """主流程"""
    print("\n" + "=" * 60)
    print("  🏎️  赛车资讯自动发布系统")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    # ============================================================
    # 步骤 1：抓取新闻
    # ============================================================
    print("【步骤 1/3】抓取新闻...")
    from fetcher import fetch_all_news, save_news_to_json

    news_list = fetch_all_news()

    if not news_list:
        print("\n[主程序] ⚠️  未抓取到任何新闻，请检查新闻源配置")
        sys.exit(1)

    save_news_to_json(news_list)
    print(f"[主程序] ✅ 步骤 1 完成，共抓取到 {len(news_list)} 条新闻\n")

    # ============================================================
    # 步骤 2：AI 处理
    # ============================================================
    print("【步骤 2/3】AI 处理新闻...")
    from ai_processor import process_news

    result = process_news(news_list)
    print(f"[主程序] ✅ 步骤 2 完成，文章标题：{result['title']}\n")

    # ============================================================
    # 步骤 3：自动发布
    # ============================================================
    auto_publish = os.getenv("AUTO_PUBLISH", "false").lower() == "true"

    if auto_publish:
        print("【步骤 3/3】自动发布到公众号...")
        from publisher import publish_draft_from_file

        success = publish_draft_from_file()
        if success:
            print("[主程序] ✅ 步骤 3 完成，文章已发布到公众号！")
        else:
            print("[主程序] ⚠️  自动发布失败，请查看错误信息")
    else:
        print("【步骤 3/3】跳过自动发布（AUTO_PUBLISH=false）")
        print("[主程序] 💡 提示：设置 AUTO_PUBLISH=true 启用自动发布")
        print("[主程序] 💡 或手动复制 data/preview.html 内容到公众号\n")

    # ============================================================
    # 完成
    # ============================================================
    print("=" * 60)
    print("  ✅  全部完成！")
    print(f"  文章标题：{result['title']}")
    print(f"  新闻条数：{result['news_count']}")
    print(f"  预览文件：data/preview.html")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[主程序] 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n[主程序] ❌ 运行出错：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
