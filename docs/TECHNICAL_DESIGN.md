# GitHub Merge Request Review Agent 技术设计

## 1. 背景与目标

本项目使用 CrewAI 构建一个自动代码评审 agent。它监听 GitHub 的 merge request 类事件，并在有新提交进入时自动拉取增量 diff，完成风险识别、评审意见生成、风险等级归类，并在 GitHub 上 @ 提交人给出修改建议。

说明：GitHub 官方名称是 Pull Request，GitLab 才叫 Merge Request。本文档中的 Merge Request 指代 GitHub Pull Request。后续如果需要兼容 GitLab，可以在事件适配层扩展 GitLab webhook 和 API client。

核心目标：

- 识别 GitHub PR 的新增提交。
- 只 review 本次新增提交对应的 diff，避免重复评论历史代码。
- 使用 CrewAI 编排多个 agent 分工完成代码评审。
- 将修改意见按高、中、低风险输出。
- 在 PR 中 @ 提交人，发布结构化 review 评论。
- 支持 webhook 签名校验、幂等处理、失败重试和审计日志。

## 2. 用户场景

1. 开发者向某个分支创建或更新 PR。
2. GitHub 触发 webhook，请求本服务。
3. 服务验证 webhook 签名和事件类型。
4. 系统判断该 PR 是否有未 review 的新提交。
5. 系统拉取新增提交的 diff 和必要上下文。
6. CrewAI 执行自动评审流程。
7. 系统在 PR 里发布一条 summary 评论，并尽量在具体代码行发布 inline review comment。
8. 评论中 @ 提交人，并把建议分为高、中、低风险。

## 3. 非目标

MVP 阶段不做以下能力：

- 不自动修改代码或直接提交修复 commit。
- 不替代人工 reviewer 的最终决策。
- 不对整个仓库做全量扫描，只关注 PR 新增 diff。
- 不保证对所有语言都有深度语义理解，优先支持常见 Web 后端和前端项目。
- 不接入 GitHub Checks 的阻塞策略，先只发表评论。

## 4. 系统架构

整体采用 Python 后端服务，当前 MVP 已跑通 GitHub App webhook 到 PR 评论的闭环：

- Web 框架：FastAPI
- 运行服务：Uvicorn
- 依赖管理：uv
- GitHub 接入：GitHub App + REST API
- 本地 webhook 调试：ngrok
- 存储：SQLite，后续可切 PostgreSQL
- LLM：DeepSeek OpenAI-compatible API
- Review 编排：当前为 `PullRequestReviewCrew` 同步流程，后续扩展为 CrewAI 多 agent 编排

```text
GitHub Webhook
      |
      v
FastAPI Webhook Endpoint
      |
      v
Event Validator / Router
      |
      v
GitHub Diff Collector
      |
      v
PullRequestReviewCrew
      |
      +-- DeepSeek LLM Review
      |
      +-- Deterministic Fallback Review
      |
      v
Risk Report + Comments
      |
      v
GitHub Review Publisher
```

## 5. GitHub 事件设计

监听事件：

- `pull_request.opened`：新 PR 创建后执行首次 review。
- `pull_request.synchronize`：PR 有新 commit push 后执行增量 review。
- `pull_request.reopened`：PR 重新打开后检查是否有未 review 提交。
- `pull_request.ready_for_review`：draft PR 变为 ready 后执行 review。

忽略事件：

- `pull_request.closed`
- `pull_request.edited`
- `pull_request.labeled`
- draft PR 中间状态更新，除非配置允许 review draft。

关键字段：

- `repository.full_name`
- `pull_request.number`
- `pull_request.head.sha`
- `pull_request.base.sha`
- `pull_request.user.login`
- `sender.login`
- `action`

## 6. 增量 Review 策略

系统需要记录每个 PR 最近一次成功 review 的 head sha。

数据表建议：

```text
review_state
- id
- repo_full_name
- pr_number
- last_reviewed_head_sha
- last_reviewed_at
- last_review_comment_id
- created_at
- updated_at
```

处理逻辑：

1. 收到 webhook 后读取当前 `head.sha`。
2. 查询 `review_state`。
3. 如果不存在记录，review 当前 PR 全部 diff。
4. 如果存在记录，并且 `last_reviewed_head_sha == head.sha`，直接跳过。
5. 如果存在记录，但 sha 不一致，拉取 `last_reviewed_head_sha...head.sha` 的 compare diff。
6. review 成功且评论发布成功后，更新 `last_reviewed_head_sha`。

这样可以避免重复 review，也能保证每次只关注新提交。

## 7. CrewAI Agent 设计

### 7.1 当前 Review Crew

当前 `PullRequestReviewCrew` 是同步执行的 workflow 边界：

1. 接收 `PullRequestReviewInput`，包含 PR metadata、文件列表、diff 文本和裁剪标记。
2. 如果配置了 `LLM_PROVIDER=deepseek`、`LLM_API_KEY`、`LLM_MODEL` 和 `LLM_BASE_URL`，优先调用 DeepSeek `/chat/completions`。
3. Prompt 要求模型只返回 JSON 对象：
   - `summary`
   - `findings[]`
   - `file_path`
   - `line`
   - `risk_level`
   - `message`
   - `reason`
4. 使用 Pydantic 校验模型输出，并复用 `build_report()` 做高、中、低风险分组。
5. 如果 LLM 请求失败、返回格式不合法或配置缺失，回退到确定性的规则版 review，确保 webhook 不因模型问题中断。

### 7.2 规划中的 CrewAI 多 Agent

CrewAI 中建议定义一个 `PullRequestReviewCrew`，由以下 agent 组成：

- `Diff Analyst`
  - 输入：PR metadata、新增 diff、文件列表。
  - 输出：变更摘要、受影响模块、潜在风险区域。

- `Code Reviewer`
  - 输入：diff、上下文文件片段、项目规则。
  - 输出：代码缺陷、可维护性问题、潜在 bug、测试缺口。

- `Security Reviewer`
  - 输入：diff、依赖变化、配置变化。
  - 输出：鉴权、注入、敏感信息、权限扩大、供应链风险。

- `Risk Classifier`
  - 输入：所有 review findings。
  - 输出：高/中/低风险分类和原因。

- `Comment Writer`
  - 输入：风险分级结果、提交人信息。
  - 输出：适合发布到 GitHub 的中文 review 评论。

### 7.3 风险等级定义

高风险：

- 可能导致生产事故、数据泄露、权限绕过或资金损失。
- 破坏公共 API、数据库 schema 或核心业务流程。
- 引入明显安全漏洞，如 SQL 注入、未授权访问、硬编码密钥。
- 删除或绕过关键测试、校验、审计逻辑。

中风险：

- 可能导致边界场景 bug、性能回退或错误状态处理。
- 影响可维护性、可观测性或异常恢复。
- 测试覆盖不足，但风险范围相对可控。
- 修改共享组件、工具函数、配置逻辑但没有充分说明。

低风险：

- 命名、格式、轻微重复、局部可读性问题。
- 建议补充注释、日志或小范围测试。
- 不影响主流程的改善建议。

### 7.4 Python Review 规范

当 PR 变更包含 `.py` 文件时，系统会把 Python 专用审查规范注入 LLM prompt，帮助模型减少泛泛建议，优先输出真实、具体、可操作的问题。

重点检查：

- 正确性：控制流、边界条件、`None` 处理、可变默认参数、资源释放、async/sync 误用。
- 安全：硬编码 secret、不安全反序列化、命令/SQL 注入、路径穿越、弱加密、鉴权绕过、敏感信息日志。
- 异常处理：异常类型是否明确、上下文是否保留、是否吞异常、重试和 timeout 是否有边界。
- 类型和契约：公开函数签名、返回类型一致性、外部输入校验、避免不必要的 `Any`。
- FastAPI：请求数据校验、异步接口中避免阻塞 I/O、依赖注入一致性、HTTP 状态码合理性。
- 数据库和状态：事务边界、幂等性、唯一性假设、schema 兼容、竞态条件。
- 测试：关键行为、安全路径、回归 case、错误分支是否有聚焦测试。
- 可维护性：小函数、清晰命名、简单分支、避免无关重构和重复逻辑。
- 可观测性：重要失败应有可行动日志，但不能暴露 secret。
- 依赖和配置：新增依赖、运行时假设、不安全默认值、应由环境变量驱动的配置。

## 8. Review 输出格式

PR summary 评论示例：

```markdown
@submitter 本次新增提交已完成自动 review，建议优先处理高风险问题。

## 高风险
- `src/auth/session.py`: 当前逻辑在 token 过期后仍可能放行请求，建议补充过期时间校验并增加测试。

## 中风险
- `src/api/order.py`: 新增接口缺少异常路径测试，建议覆盖库存不足和支付失败场景。

## 低风险
- `src/utils/format.py`: 函数命名可以更明确，建议从 `format_data` 改为 `format_order_payload`。

## 总结
本次变更主要影响订单提交流程，建议在合并前至少补齐高风险项对应测试。
```

Inline comment 优先级：

1. 高风险问题尽量发布 inline comment。
2. 中风险如果能定位到具体行，也发布 inline comment。
3. 低风险默认放在 summary，避免过多噪音。

## 9. GitHub 评论发布策略

推荐使用 GitHub Review API：

- 对具体代码行使用 `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`。
- 对整体总结使用 issue comment API：`POST /repos/{owner}/{repo}/issues/{issue_number}/comments`。

评论发布需要注意：

- GitHub inline comment 必须基于当前 diff position 或 line 信息。
- 如果无法准确定位代码行，则降级为 summary 评论。
- 评论内容需要包含 marker，例如 `<!-- crewai-review-agent -->`，便于后续更新或去重。
- 同一个 head sha 只发布一次 review 结果。

## 10. 配置项

建议使用环境变量：

```text
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY_PATH=
GITHUB_WEBHOOK_SECRET=
GITHUB_INSTALLATION_ID=
GITHUB_API_URL=https://api.github.com
LLM_PROVIDER=
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=https://api.deepseek.com
DATABASE_URL=sqlite:///./review_agent.db
REVIEW_DRAFT_PR=false
MAX_DIFF_LINES=3000
```

本地调试还需要：

- 本地启动服务：`uv run uvicorn app.main:app --reload --port 8000`
- 启动 ngrok：`ngrok http 8000`
- GitHub App Webhook URL：`https://<ngrok-domain>/webhooks/github`
- GitHub App Webhook Secret 与 `GITHUB_WEBHOOK_SECRET` 保持一致。
- GitHub App 至少安装到目标仓库，并订阅 `Pull request` 事件。

## 11. 安全设计

Webhook 安全：

- 必须校验 `X-Hub-Signature-256`。
- 必须校验 `X-GitHub-Event` 和 delivery id。
- 对 `X-GitHub-Delivery` 做幂等记录，避免重复处理。

GitHub 权限：

- 使用 GitHub App，不建议使用个人 token。
- 最小权限：
  - Pull requests: read/write
  - Contents: read
  - Issues: write
  - Metadata: read

LLM 安全：

- 不把 secrets、完整 `.env`、私钥内容发送给 LLM。
- diff 超过限制时做文件级裁剪，并标记被裁剪内容。
- 支持仓库级 allowlist，避免 webhook 被滥用。

## 12. 错误处理

常见失败场景：

- GitHub webhook 重复投递：通过 delivery id 幂等跳过。
- GitHub API rate limit：任务进入重试队列，指数退避。
- diff 太大：只 review 高风险文件类型，评论中说明裁剪范围。
- LLM 调用失败：当前降级为确定性 fallback review，仍可发布 summary 评论，避免 webhook 中断。
- inline comment 定位失败：降级为 summary 评论。

## 13. 项目结构建议

```text
github-mr-review-agent/
  docs/
    TECHNICAL_DESIGN.md
  app/
    main.py
    config.py
    github/
      client.py
      webhook.py
      comments.py
    review/
      crew.py
      tasks.py
      schemas.py
      risk.py
    storage/
      database.py
      models.py
  tests/
    test_webhook_signature.py
    test_incremental_review.py
    test_risk_classifier.py
  pyproject.toml
  README.md
  .env.example
```

## 14. MVP 开发里程碑

第一阶段：基础 webhook 服务

- 搭建 FastAPI 项目。
- 实现 GitHub webhook endpoint。
- 实现签名校验和事件过滤。
- 保存 delivery id 和 review state。

第二阶段：GitHub diff 拉取

- 接入 GitHub App 鉴权。
- 拉取 PR metadata、files、commits 和 compare diff。
- 实现新增提交识别。

第三阶段：DeepSeek review 流程

- 接入 DeepSeek OpenAI-compatible API。
- 输出结构化 findings。
- 实现高中低风险分类。
- 保留确定性 fallback review。

第四阶段：评论发布

- 发布 PR summary 评论。
- 增加评论去重 marker。
- 支持更新已有 summary 评论。
- inline comment 作为后续扩展。

第五阶段：测试和部署

- 增加单元测试和 webhook fixture。
- 提供 Dockerfile 和部署说明。
- 增加日志、重试和错误告警。

## 15. 后续扩展

- 支持 GitLab Merge Request。
- 支持仓库级 review 规则文件，例如 `.review-agent.yml`。
- 接入 GitHub Checks，在高风险问题存在时阻止合并。
- 支持自动生成修复建议 patch。
- 支持多语言规则插件，例如 Python、TypeScript、Go、Java。
- 支持把 review 结果同步到 Slack、飞书或 Jira。
