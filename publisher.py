"""
公众号自动发布模块
使用 Playwright 浏览器自动化发布文章到微信公众号
适用于未认证订阅号（无 API 权限）

注意：首次运行需要扫码登录，Cookie 会保存供后续使用
"""

import os
import json
import time
from typing import Optional


def publish_to_wechat(title: str, content: str, cover_image: Optional[str] = None) -> bool:
    """
    使用 Playwright 自动发布文章到公众号
    
    Args:
        title: 文章标题
        content: 文章 HTML 内容
        cover_image: 封面图路径（可选）
    
    Returns:
        bool: 是否发布成功
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[发布] 错误：未安装 Playwright，请运行：pip install playwright && playwright install chromium")
        return False

    cookie_path = os.getenv("WECHAT_COOKIE_PATH", "data/wechat_cookies.json")
    os.makedirs(os.path.dirname(cookie_path), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 首次运行建议非 headless 模式观察
        context = browser.new_context()

        # 尝试加载已保存的 Cookie
        if os.path.exists(cookie_path):
            print("[发布] 加载已保存的登录状态...")
            with open(cookie_path, "r") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)

        page = context.new_page()

        # 访问公众号后台
        print("[发布] 正在打开公众号后台...")
        page.goto("https://mp.weixin.qq.com/", timeout=30000)
        time.sleep(2)

        # 检查是否需要登录
        if "登录" in page.title() or page.url.startswith("https://mp.weixin.qq.com/cgi-bin/bizlogin"):
            print("[发布] 需要登录！请在浏览器中扫码登录...")
            print("[发布] 登录完成后，按 Enter 继续...")
            input()  # 等待用户扫码

            # 保存 Cookie
            cookies = context.cookies()
            with open(cookie_path, "w") as f:
                json.dump(cookies, f)
            print(f"[发布] 登录状态已保存到：{cookie_path}")

        # 进入图文消息页面
        print("[发布] 进入图文消息页面...")
        page.click("text=图文消息", timeout=10000)
        time.sleep(2)

        # 点击"新建图文"
        page.click("text=新建图文", timeout=10000)
        time.sleep(2)

        # 填写标题
        print(f"[发布] 填写标题：{title}")
        page.fill('input[placeholder*="标题"]', title)
        time.sleep(1)

        # 填写作者（可选）
        author = os.getenv("ARTICLE_AUTHOR", "赛车日报")
        try:
            page.fill('input[placeholder*="作者"]', author)
        except Exception:
            pass

        # 填写正文（切换到 HTML 模式）
        print("[发布] 填写正文内容...")
        # 点击 HTML 模式按钮（公众号编辑器通常有"HTML"按钮）
        try:
            page.click("text=HTML", timeout=5000)
            time.sleep(1)
            # 填写 HTML 内容
            page.fill("textarea", content)
        except Exception:
            # 如果没有 HTML 模式，直接粘贴到富文本编辑器
            page.evaluate(f"document.querySelector('.edui-body .edui-box').innerHTML = `{content}`")

        time.sleep(2)

        # 上传封面图（如果有）
        if cover_image and os.path.exists(cover_image):
            print("[发布] 上传封面图...")
            try:
                page.click("text=上传封面")
                page.set_input_files('input[type="file"]', cover_image)
                time.sleep(3)
            except Exception as e:
                print(f"[发布] 上传封面失败：{e}")

        # 设置摘要
        summary = content[:50].replace("<", "").replace(">", "")
        try:
            page.fill('textarea[placeholder*="摘要"]', summary)
        except Exception:
            pass

        # 定时发布（每天 10 点）
        print("[发布] 设置定时发布...")
        try:
            page.click("text=定时群发")
            # 选择时间（这里需要根据实际页面调整）
            page.fill('input[placeholder*="时间"]', "10:00")
        except Exception:
            print("[发布] 警告：无法设置定时发布，将保存为草稿")

        # 保存草稿（不立即发布，方便审核）
        print("[发布] 保存草稿...")
        page.click("text=保存", timeout=10000)
        time.sleep(2)

        print("[发布] ✅ 文章已保存为草稿！")
        print("[发布] 请登录公众号后台审核并发布：https://mp.weixin.qq.com/")

        browser.close()
        return True


def publish_draft_from_file(json_path: str = "data/processed_article.json") -> bool:
    """从 JSON 文件读取文章内容并发布"""
    with open(json_path, "r", encoding="utf-8") as f:
        article = json.load(f)

    return publish_to_wechat(
        title=article["title"],
        content=article["content"],
    )


if __name__ == "__main__":
    # 测试发布
    import sys
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = "data/processed_article.json"

    if not os.path.exists(json_path):
        print(f"[发布] 错误：找不到文件 {json_path}")
        print("[发布] 请先运行 ai_processor.py 生成文章")
        sys.exit(1)

    publish_draft_from_file(json_path)
