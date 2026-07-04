# 赛车资讯自动发布系统 - 配置指南

本指南面向**无编程基础**的用户，手把手教你完成配置。

## 第一步：获取 AI API 密钥

AI 用于处理新闻（翻译、摘要、排版），推荐使用 **DeepSeek API**（最便宜）。

### 获取 DeepSeek API Key

1. 访问 [https://platform.deepseek.com/](https://platform.deepseek.com/)
2. 注册账号并登录
3. 点击「API Keys」→「创建 API Key」
4. 复制生成的 Key（格式类似 `sk-xxxxxxxx`）

> 💰 费用参考：处理 10 条新闻约消耗 5000 tokens，费用约 ¥0.14

## 第二步：准备新闻源（无需配置）

项目已内置以下新闻源，开箱即用：

| 赛事 | 来源 | 状态 |
|------|------|------|
| F1 | BBC Sport RSS | ✅ 已配置 |
| F1 | Motorsport RSS | ✅ 已配置 |
| 中国GT | gt-world-challenge.com.cn | ✅ 已配置 |

## 第三步：配置自动发布

### 方案 A：半自动（推荐新手）

每天自动生成排版好的文章，发送到你的邮箱/微信，你只需复制粘贴到公众号（耗时 < 2 分钟）。

1. 打开 `.env` 文件
2. 设置 `AUTO_PUBLISH=false`
3. 设置 `ENABLE_EMAIL_NOTIFY=true` 并填写 `EMAIL_TO`
4. 每天 10 点你会收到邮件，复制内容发布即可

### 方案 B：全自动（需要扫码）

使用 Playwright 浏览器自动化发布，每 1-2 周需要重新扫码一次。

1. 打开 `.env` 文件
2. 设置 `AUTO_PUBLISH=true`
3. 首次运行时，程序会打开浏览器让你扫码登录
4. 登录后 Cookie 自动保存，后续无需扫码

## 第四步：部署到 GitHub Actions（每天 10 点自动运行）

### 4.1 创建 GitHub 仓库

1. 访问 [https://github.com/](https://github.com/) 并登录
2. 点击右上角「+」→「New repository」
3. 仓库名填写 `racing-news-bot`
4. 选择「Public」或「Private」
5. 点击「Create repository」

### 4.2 上传代码

下载本项目的所有文件，然后在本地运行：

```bash
git init
git add .
git commit -m "初始化赛车资讯自动发布系统"
git remote add origin https://github.com/你的用户名/racing-news-bot.git
git push -u origin main
```

### 4.3 配置 GitHub Secrets

在 GitHub 仓库页面：

1. 点击「Settings」→「Secrets and variables」→「Actions」
2. 点击「New repository secret」
3. 添加以下 Secret：

| Name | Value |
|------|-------|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key |

### 4.4 启用 GitHub Actions

1. 在仓库页面点击「Actions」标签
2. 如果显示「This workflow has errors」，检查 `.github/workflows/daily.yml` 是否正确
3. 如果一切正常，Actions 已自动启用

### 4.5 测试运行

1. 在仓库页面点击「Actions」
2. 选择「赛车资讯每日发布」工作流
3. 点击「Run workflow」→「Run workflow」手动触发一次测试

## 第五步：验证运行结果

### 查看运行日志

1. 在仓库页面点击「Actions」
2. 点击最近一次运行记录
3. 点击「build」步骤查看详细日志

### 检查生成的文章

运行成功后，你可以在以下位置查看生成的文章：

- GitHub Actions 日志中会显示文章标题
- 如果配置了邮件通知，会收到排版好的文章

## 常见问题

### Q1：GitHub Actions 是免费的吗？

是的，GitHub Actions 对个人用户免费（每月 2000 分钟）。

### Q2：新闻抓取失败怎么办？

- 检查网络连接（GitHub Actions 服务器在国外，访问国内网站可能较慢）
- 尝试增加更多新闻源（编辑 `fetcher.py`）
- 查看 GitHub Actions 日志中的错误信息

### Q3：AI 处理失败怎么办？

- 检查 `DEEPSEEK_API_KEY` 是否正确
- 检查账户余额是否充足
- 尝试切换到通义千问 API

### Q4：自动发布失败怎么办？

- 未认证订阅号无法使用 API，只能使用浏览器自动化方案
- 如果 Playwright 方案不稳定，建议改用半自动方案
- 查看 `publisher.py` 中的错误信息

## 进阶配置

### 添加更多新闻源

编辑 `fetcher.py`，在 `F1_RSS_SOURCES` 列表中添加更多 RSS 源：

```python
{
    "name": "新来源名称",
    "url": "http://example.com/rss.xml",
    "lang": "en",  # 或 "zh"
    "category": "F1",
}
```

### 自定义文章模板

编辑 `ai_processor.py` 中的 `generate_wechat_article()` 函数，修改 HTML 模板。

### 修改发布时间

编辑 `.github/workflows/daily.yml`，修改 `cron` 表达式：

```yaml
# 每天 10:00 北京时间（UTC+8 = 02:00 UTC）
schedule:
  - cron: '0 2 * * *'
```

## 支持与反馈

如果遇到问题，可以：

1. 查看 GitHub Actions 运行日志
2. 检查 `.env` 配置是否正确
3. 在 GitHub 仓库中提 Issue

---

**祝你公众号运营顺利！🏎️**
