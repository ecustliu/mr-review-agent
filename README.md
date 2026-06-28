# GitHub MR Review Agent

基于 FastAPI、GitHub App 和 DeepSeek 的 GitHub Pull Request 自动评审服务。

服务通过 GitHub App 接收 PR webhook，拉取 PR diff，调用 DeepSeek 生成结构化 review 结果，并用 GitHub App bot 身份在 PR 下发布或更新 summary 评论。

## 技术栈

- Python 3.10+
- FastAPI + Uvicorn：提供 webhook HTTP 服务。
- uv：管理 Python 依赖、虚拟环境和测试命令。
- GitHub App：接收 webhook，使用 installation token 访问仓库和发布评论。
- httpx：调用 GitHub API 和 DeepSeek OpenAI-compatible API。
- DeepSeek：生成 PR review summary 和 findings。
- Pydantic / pydantic-settings：配置和数据结构校验。
- SQLAlchemy + SQLite：记录 webhook delivery 和 PR review 状态。
- pytest：单元测试。
- ngrok：本地开发时把 `localhost:8000` 暴露成公网 HTTPS webhook 地址。

## Quick Start

安装依赖：

```bash
uv sync --dev --extra agent
cp .env.example .env
```

填写 `.env`，至少需要：

```env
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY_PATH=
GITHUB_WEBHOOK_SECRET=
GITHUB_INSTALLATION_ID=
GITHUB_API_URL=https://api.github.com

LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

启动本地服务：

```bash
uv run uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

预期返回：

```json
{"status":"ok"}
```

## 本地 Webhook 调试

GitHub 无法直接访问本机的 `localhost:8000`，本地调试需要用 ngrok 暴露公网地址：

```bash
ngrok http 8000
```

ngrok 会输出类似地址：

```text
https://example.ngrok-free.dev -> http://localhost:8000
```

GitHub App 的 Webhook URL 填：

```text
https://example.ngrok-free.dev/webhooks/github
```

GitHub App 的 Webhook Secret 必须和 `.env` 完全一致：

```env
GITHUB_WEBHOOK_SECRET=同一串随机字符串
```

可以用下面命令生成：

```bash
openssl rand -hex 32
```

## GitHub App 配置

Repository permissions：

- Contents: Read-only
- Pull requests: Read and write
- Issues: Read and write
- Metadata: Read-only

Subscribe to events：

- Pull request

安装 GitHub App 时，需要授权到要测试的仓库。安装页面 URL 中的数字就是 `GITHUB_INSTALLATION_ID`，例如：

```text
https://github.com/settings/installations/12345678
```

## 触发 Review

1. 确保本地 FastAPI 服务和 ngrok 都在运行。
2. GitHub App Webhook URL 指向 ngrok 的 `/webhooks/github`。
3. GitHub App 已安装到目标仓库，并订阅 `Pull request` 事件。
4. 新建或更新 PR。

成功后，PR 下会出现 `code-review-crew-agent[bot]` 的 summary 评论。

## 测试

运行完整测试：

```bash
uv run pytest
```

## Webhook Endpoint

```text
POST /webhooks/github
```

## 当前能力

- GitHub webhook 签名校验。
- PR 事件过滤和 draft PR 控制。
- delivery id 幂等记录。
- PR `head.sha` 增量 review 状态判断。
- GitHub App installation token 鉴权。
- 首次 PR diff 和新增提交 compare diff 拉取。
- diff 行数裁剪和裁剪提示。
- 带 marker 的 PR summary 评论创建/更新。
- DeepSeek API 配置存在时优先生成模型审查结果。
- DeepSeek 请求失败或配置缺失时，回退到确定性的规则版 review。

尚未完成：

- inline review comment 定位和发布。
- 任务队列、重试和部署配置。
- 更完整的 CrewAI 多 agent 任务编排。
