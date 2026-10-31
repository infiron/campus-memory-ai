# 校园集体记忆 AI 传承助手

**项目形态：** 可在本地运行的 Web 原型（FastAPI + SQLAlchemy + SQLite），前端为独立 HTML/CSS/JavaScript 静态资源。核心 API 已按模块拆分，并预留 OpenAI-compatible 模型与向量嵌入服务接口。此版本重点打通项目需求文档 V1.0 的 P0 核心闭环。

> **请先阅读：** 数据库预置的课程、学生经验、M1–M4 评分样例和外部链接均为合成演示数据。`example.org` URL 是占位地址。不能把这些记录称作真实校内调查、真实学生经验或已经获得授权的真实外部资料。正式演示前请替换为获准资料，或持续显示“演示数据”标记。

## 1. 运行环境

- Python 3.11 或更新版本
- 浏览器：Chrome / Edge；移动浏览器可用于基本页面检查
- 默认 SQLite，无需先安装数据库服务器
- 可选：OpenAI-compatible 对话模型和 Embedding 服务；未配置时系统将采用规则抽取、关键词检索与基于证据片段的模板回答

## 2. 本地启动

**快捷启动：** Windows 双击项目根目录的 `run_local.bat`；macOS/Linux/Ubuntu 在项目根目录运行 `./run_local.sh`。脚本会建立虚拟环境、安装依赖并在缺少时复制 `.env.example`。第一次启动需要网络下载 Python 依赖。

### Windows PowerShell

```powershell
cd campus_memory_ai\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### macOS / Linux / Ubuntu

```bash
cd campus_memory_ai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开：<http://127.0.0.1:8000>  
API 文档：<http://127.0.0.1:8000/docs>  
健康检查：<http://127.0.0.1:8000/api/health>

首次启动时会建立 `backend/campus_memory.db` 并加载合成演示数据。默认包含至少 3 门课程、多个学期、30 条以上标明“演示/合成数据”的已发布可用示例，以及待审核负向样例。它们只用于演示检索、状态过滤和评分流程，不代表真实校园调查。不要把本地数据库文件、`.env`、密钥或真实个人信息提交到公开仓库。

## 3. 本地演示账号

仅本地演示使用，四个账号的初始密码都是 `demo123!`。前端右上角可切换角色。

| 用户名 | 角色 | 典型验证操作 |
|---|---|---|
| `reader_demo` | 查询者 | 搜索公开经验、问答、查看引用 |
| `contributor_demo` | 查询者 + 贡献者 | 提交原文、确认 AI 字段、查看个人记录 |
| `reviewer_demo` | 查询者 + 审核员 | 审核队列、通过/退回/拒绝、反馈处理 |
| `admin_demo` | 查询者 + 审核员 + 管理员 | 来源许可、角色和规则配置、日志与维护建议 |

所有 API 都在后端校验角色。仅隐藏前端按钮并不构成权限控制。生产部署须禁用演示数据、创建安全管理员账号、设置强 `SECRET_KEY`、使用 HTTPS，并完成部署环境的安全审查。匿名署名是默认值；选择公开昵称会记录在经验中。若文本检测到邮箱或常见手机号，审核发布会被阻止；贡献者可修订当前文本，首次提交快照仍保留为私有记录。此规则检测只是初步防护，不替代人工隐私审核。

## 4. 配置 AI 服务（可选）

复制 `.env.example` 后，根据获准的模型服务填写以下变量。`AI_BASE_URL` 应是服务提供的 OpenAI-compatible API 基础地址，通常以 `/v1` 结尾。模型名称必须由你所使用的服务提供方确认；本项目不预设你拥有任何模型配额。

```dotenv
AI_BASE_URL=https://your-approved-provider.example/v1
AI_API_KEY=replace-with-your-key
AI_MODEL=replace-with-an-available-chat-model
AI_EMBEDDING_MODEL=replace-with-an-available-embedding-model
```

- 配置 `AI_MODEL` 后，系统会尝试用模型整理字段和生成有证据上下文的回答；模型失败时会降级。
- 配置 `AI_EMBEDDING_MODEL` 后，问答召回尝试结合关键词与语义相似度；调用失败或未配置时降级为关键词检索。
- API 密钥只从环境变量读取，不应写入源码、日志、README 或公开截图。
- 模型输出仍需校验与人工审核，不允许覆盖提交原文。

## 5. 首期功能路线

### 已进入当前原型（P0 代码路径）

- 按课程、学期、关键词检索，过滤未发布、下架和许可失效内容。
- 提交并先保存原文，再尝试 AI 结构化抽取；缺失字段使用“未提及”。
- 贡献者编辑抽取字段并确认后送审。
- 审核员通过、退回、拒绝和下架；禁止审核本人提交的经验。
- 外部来源登记、许可状态与转载归并；仅链接内容不进入 RAG、不计分；管理员可登记外链待核验/有效/失效状态，标记失效后不再进入公开搜索、评分与 RAG。外链有效性是人工核验，不是自动网络探测。
- RAG 问答保存回答与 `EvidenceLink` 关联；无证据时明确提示不足。
- A/S/T/D 可复算评分、M1–M4 参考样例与“最可信参考”门槛。
- 基础审核日志、角色 API 校验、下架后查询过滤、管理与交付检查界面。

### P1 / P2 分阶段模块

- P1 反馈与纠错：当前可提交反馈、生成反馈 ID、记录处理状态；“已更新”仍表示处理结果记录，尚未自动执行被反馈内容的实质修改。
- P1 完整操作日志：角色/评分配置变更日志已有基础实现；还需按正式部署要求强化日志访问审计与保留策略。
- P1 近似重复与过期复核：仅生成候选并提醒人工复核；不会自动合并、删除或覆盖内容。
- P2 反馈统计：仅输出聚合数量，不包含个人排名或个人敏感信息；复杂分析与可视化仍需后续扩展。

## 6. 评分规则

默认权重来自需求文档 V1.0：

`C = 0.40 × A + 0.25 × S + 0.20 × T + 0.15 × D`

默认样例（评分日固定为 2026-10-14）：

| 样例 | A | S | T | D | C | 处理 |
|---|---:|---:|---:|---:|---:|---|
| M1 | 80 | 100 | 100 | 70 | 87.5 | 较高；满足条件时为最可信参考 |
| M2 | 80 | 100 | 60 | 80 | 81.0 | 较高；时间较早，未注明经历学期 |
| M3 | — | — | — | — | 不计分 | 转载归并至 M2，不重复计分 |
| M4 | 50 | 100 | 30 | 40 | 57.0 | 较低，仅作补充 |

评分表示证据质量，不是事实为真的概率。主张范围不同的记录不能无条件互相加成。`claim_group` 由审核员或来源登记人员明确指定；来源独立性和冲突也需人工确认。

## 7. 测试

在 `backend` 目录执行：

```bash
pip install -r requirements.txt
pytest -q
```

测试使用独立测试数据库，不会用演示记录以外的资料冒充真实数据。测试覆盖健康检查、M1–M4 评分复算、权限过滤、仅链接来源隔离、证据不足、提交—确认—审核—发布闭环、角色权限和许可撤销后同步过滤。它们是自动化回归测试，不替代完整的 AT-01 至 AT-18、浏览器兼容性、30 题人工评估集或云端验收。

30 题 AI 评估集模板见 `data/ai_evaluation_set.json`。运行后必须记录真实结果、缺陷和复测结论；不能预先把尚未执行的验收写成通过。

## 8. Docker 本地运行

在项目根目录：

```bash
cp .env.example .env
docker compose up --build
```

打开 <http://localhost:8000>。正式上线前把 `APP_ENV` 设置为 `production`、`SEED_DEMO_DATA=false`、设置强密钥并执行部署与安全核查。首次生产环境的管理员账号应通过 `scripts/create_admin.py` 安全创建，不要沿用演示账号。使用 Docker Compose 时，先确认 `APP_ENV=production`、`SEED_DEMO_DATA=false`、强随机 `SECRET_KEY` 与数据库卷配置，再执行 `docker compose exec campus-memory python /app/scripts/create_admin.py`；该脚本会交互式读取强密码，不会打印密码。

## 9. 许可与第三方依赖说明

项目自己的代码目前尚未指定对外开源许可证，因此不要把该仓库视为已授权公开再分发的成品。`backend/requirements.txt` 固定本次测试使用的直接 Python 依赖版本；`THIRD_PARTY_NOTICES.md` 记录直接依赖的上游许可证。正式分发前仍需核查完整传递依赖并生成最终 SBOM/声明，同时由团队确定项目代码许可证。当前仓库不包含获准的真实外部回答正文；示例链接使用 `example.org` 占位符。

## 10. 华为云 / CodeArts 交付注意

本地原型并不代表已经完成华为云部署。正式交付仍需根据赛事账号和配额确认 CodeArts 开发流程、云端数据库（如 RDS）、可选缓存（Redis）、模型服务、在线 Demo、依赖/部署/使用说明、许可证及无密钥源码。请保存实际构建与部署记录，不在报告中声称未发生的部署或测试已经完成。

**实现与方案说明：** 当前原型使用独立静态 HTML/CSS/JavaScript 前端，而非方案 PPT 中建议的 Vue 3 + Vite；后端仍是 FastAPI。这样先免去 Node 构建步骤，便于快速运行与验收核心流程，但这是一个有意的原型简化，不应在汇报中说已经完成 Vue 版。如果教师要求严格按 Vue 技术栈交付，下一阶段需迁移前端并重新运行兼容性与端到端测试。

## 11. 目录

```text
campus_memory_ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI routes / auth / lifecycle
│   │   ├── models.py               # SQLAlchemy data model
│   │   ├── security.py             # PBKDF2 password hashes + signed token
│   │   ├── seed.py                 # clearly marked demo records
│   │   ├── services/
│   │   │   ├── ai.py               # extraction / grounded answer fallback
│   │   │   ├── embeddings.py        # optional semantic retrieval adapter
│   │   │   ├── retrieval.py         # public filtering / retrieval
│   │   │   └── scoring.py           # A/S/T/D + rules version
│   │   └── static/                 # responsive browser interface
│   ├── tests/                      # acceptance-oriented regression tests
│   ├── requirements.txt
│   └── .env.example
├── data/ai_evaluation_set.json
├── scripts/create_admin.py
├── run_local.bat                 # Windows 快捷启动
├── run_local.sh                  # macOS/Linux 快捷启动
├── Dockerfile
├── docker-compose.yml
├── REQUIREMENTS_TRACEABILITY.md
├── IMPLEMENTATION_STATUS.md
├── TEST_REPORT.md
├── THIRD_PARTY_NOTICES.md
├── CODEARTS_HANDOFF.md
└── README.md
```
