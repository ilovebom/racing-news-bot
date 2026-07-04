# 赛车资讯自动发布系统

每天自动抓取 F1 和中国 GT 世界挑战赛新闻，AI 处理后在公众号发布。

## 功能特点

- 🏎️ **多源抓取**：F1 官方 RSS + 中国 GT 世界挑战赛官网
- 🤖 **AI 处理**：自动翻译、摘要、生成公众号排版
- ⏰ **定时运行**：GitHub Actions 每天 10 点自动运行
- 📱 **自动发布**：支持浏览器自动化发布到公众号

## 文件说明

| 文件 | 说明 |
|------|------|
| `fetcher.py` | 新闻抓取模块 |
| `ai_processor.py` | AI 内容处理模块 |
| `publisher.py` | 公众号自动发布模块 |
| `main.py` | 主程序入口 |
| `requirements.txt` | Python 依赖 |
| `.env.example` | 环境变量模板 |
| `.github/workflows/daily.yml` | GitHub Actions 定时任务 |

## 快速开始

1. 复制 `.env.example` 为 `.env`，填写 API 密钥
2. 安装依赖：`pip install -r requirements.txt`
3. 运行测试：`python main.py`
4. 部署到 GitHub Actions（详见 `setup_guide.md`）

## 新闻来源

- F1：BBC Sport RSS、Motorsport RSS
- 中国 GT：gt-world-challenge.com.cn 官网
