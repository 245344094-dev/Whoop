# Whoop 每日身体报告 - GitHub Actions + Server酱

每天自动拉取 Whoop 数据，推送报告到微信，**不需要开电脑**。

## 部署步骤

### 1. 注册 Server酱，获取 SendKey

1. 打开 https://sct.ftqq.com/
2. 用微信扫码登录
3. 在「发送消息」页面复制你的 **SendKey**（形如 `SCT123456abcdef...`）

### 2. 在 GitHub 创建仓库

1. 打开 https://github.com/new
2. 仓库名随意，比如 `whoop-report`
3. 选择 **Private**（私有仓库，保护 token 安全）
4. 勾选 **Add a README file**
5. 点击 **Create repository**

### 3. 上传文件

把以下两个文件上传到仓库：

- `whoop_report.py` → 放在仓库根目录
- `.github/workflows/whoop-daily.yml` → 放在 `.github/workflows/` 目录下

（也可以用 git push，见下方「用命令行上传」）

### 4. 上传初始 Token 文件

把 `whoop_token.json` 上传到仓库根目录。这个文件包含当前的 refresh_token，脚本会用它自动刷新。

### 5. 创建 GitHub Personal Access Token (PAT)

为了让脚本每次运行后能把刷新的 token 写回仓库（保持长期可用），需要一个 PAT：

1. 打开 https://github.com/settings/tokens?type=beta（Fine-grained tokens）
2. 点击 **Generate new token**
3. 名称随意，如 `whoop-token-write`
4. Repository access → 选 **Only select repositories** → 选你刚创建的 `whoop-report`
5. Permissions → Repository permissions → **Contents: Read and write**
6. 点击 **Generate token**，复制 token（形如 `github_pat_xxxx...`）

### 6. 配置 GitHub Secrets

在仓库页面：Settings → Secrets and variables → Actions → New repository secret

添加以下 4 个 secret：

| Secret 名称 | 值 |
|---|---|
| `WHOOP_CLIENT_ID` | `c687642d-38a9-4ae2-afb5-79d1828aa081` |
| `WHOOP_CLIENT_SECRET` | `a6c2af3c646fc98aef04aa5584ee7f7d12f0ebb97722fc1e7fe686aad256df3a` |
| `SERVERCHAN_KEY` | 你在步骤 1 获取的 SendKey |
| `GH_PAT` | 你在步骤 5 获取的 PAT |

### 7. 手动触发测试

在仓库页面：Actions → 左侧选 `Whoop Daily Report` → 点击 `Run workflow` → 确认

等 1-2 分钟，查看运行日志。如果成功，你的微信会收到一条 Whoop 报告推送。

### 8. 确认定时触发

workflow 配置了每天 UTC 00:00（北京时间 08:00）自动运行。之后每天早上 8 点微信会自动收到报告。

> ⚠️ GitHub Actions 的 cron 不保证精确到秒，可能有几分钟到十几分钟的延迟，属于正常现象。

---

## 用命令行上传（可选）

如果你本地有 git，可以更快：

```bash
# 克隆空仓库
git clone https://github.com/你的用户名/whoop-report.git
cd whoop-report

# 复制文件
cp /path/to/whoop_report.py .
cp /path/to/whoop_token.json .
mkdir -p .github/workflows
cp /path/to/whoop-daily.yml .github/workflows/

# 提交推送
git add .
git commit -m "Whoop daily report setup"
git push
```

---

## Token 过期怎么办？

正常情况下不需要手动处理：
- 脚本每次运行会用 `refresh_token` 自动获取新的 `access_token`
- 新的 token 会被写回仓库的 `whoop_token.json`，下次运行继续用
- Whoop 的 refresh_token 有 `offline` scope，可以长期刷新

如果 refresh_token 本身过期（极少见，通常数月甚至更久），你会收到 Actions 运行失败的邮件通知。届时需要重新走一次 OAuth 授权流程获取新 token，更新仓库里的 `whoop_token.json`。

---

## 文件说明

| 文件 | 用途 |
|---|---|
| `whoop_report.py` | 主脚本：刷新 token → 拉数据 → 生成报告 → 推送 Server酱 → 写回 token |
| `.github/workflows/whoop-daily.yml` | GitHub Actions 定时任务，每天 08:00 触发 |
| `whoop_token.json` | OAuth token 存储（含 refresh_token，自动更新） |
