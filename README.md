# GitHub MR Review Agent

基于 FastAPI 和 CrewAI 的 GitHub Pull Request 自动评审服务骨架。

## Quick Start

```bash
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload
```

如果要安装 CrewAI 运行真实 agent 流程：

```bash
uv sync --dev --extra agent
```

运行测试：

```bash
uv run pytest
```

GitHub webhook endpoint:

```text
POST /webhooks/github
```

当前骨架已包含：

- GitHub webhook 签名校验。
- PR 事件过滤和 draft PR 控制。
- delivery id 幂等记录。
- PR `head.sha` 增量 review 状态判断。
- GitHub App installation token 鉴权。
- 首次 PR diff 和新增提交 compare diff 拉取。
- diff 行数裁剪和裁剪提示。
- 带 marker 的 PR summary 评论创建/更新。
- CrewAI review 流程占位和结构化风险输出。

尚未完成：

- 真实 CrewAI 多 agent 任务编排。
- inline review comment 定位和发布。
- 任务队列、重试和部署配置。
