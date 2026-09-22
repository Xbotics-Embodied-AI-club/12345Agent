# 12345 热线工单智能生成与转派辅助智能体（Demo v1）

群众诉求（文本 / 录音）→ 诉求理解 → 工单生成 → 分类与承办单位推荐 → 回复辅助 → 工作人员审核确认，全流程以 `case_id` 串联。后端 FastAPI + SQLite，前端 React + TypeScript + Vite。

> 可靠性优先：有 LLM Key 走大模型，无 Key **自动回退确定性本地引擎**；ASR 以「文件名→样例精确匹配」为主、whisper 为辅、模拟转写为兜底。所有 AI 产出标注 `source`（llm / local-engine），ASR 来源标注 `transcript_source`。

## 首页与导航

- `/`：工作流总入口、工单状态 KPI、在途工单接管列表与分类分布。
- `/pipeline`：原有六步工单工作台；支持 `/pipeline?case={case_id}` 加载并定位已有工单。
- `/data`：部门规则搜索、详情、编辑与删除；保存后同步更新 JSON 和部门规则 RAG 索引。
- 生产构建由 FastAPI 托管，以上页面路径可直接访问和刷新。

## 首页展示数据接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/meta` | 顶部引擎状态：显示 `engine_mode`，接口失败时显示 `local-engine` |
| GET | `/api/departments/rules` | 规则文件名：接口字段 `filename`，当前页面显示 `department_rules.json` |
| GET | `/api/departments/rules` | 部门规则数量：`rules.length` |
| GET | `/api/departments/rules` | 规则版本：优先取 `rules[0].version`，为空时取 `schema_version` |
| GET | `/api/departments/rules` | 最近更新时间：`updated_at`，页面格式为 `MM/DD` |
| GET | `/api/cases` | 工单总数：返回的工单数组长度 |
| GET | `/api/cases` | 在途工单：工单总数减去 `confirmed=true` 的工单数 |
| GET | `/api/cases` | 已确认完成：`confirmed=true` 的工单数 |
| GET | `/api/cases` | 紧急工单：`understanding.urgent=true` 的工单数 |
| GET | `/api/cases` | 概览进度条：在途工单数除以工单总数 |
| GET | `/api/cases` | “已录入”数量：未完成、未进入人工复核，且无 `reply`、`classification`、`work_order` 的工单数 |
| GET | `/api/cases` | “已生成工单”数量：未完成、未进入人工复核、无 `reply` 和 `classification`，但存在 `work_order` 的工单数 |
| GET | `/api/cases` | “已分派待处理”数量：未完成、未进入人工复核、无 `reply`，但存在 `classification` 的工单数 |
| GET | `/api/cases` | “已生成回复”数量：未完成、未进入人工复核，且存在 `reply` 的工单数 |
| GET | `/api/cases` | “待最终确认”数量：未完成且 `next_action=human_review` 的工单数 |
| GET | `/api/cases` | 在途工单列表总数：`confirmed` 不为 `true` 的工单数 |
| GET | `/api/cases` | 工单编号：`case_id` |
| GET | `/api/cases` | 工单状态：根据 `confirmed`、`next_action`、`reply`、`classification`、`work_order` 依次判断 |
| GET | `/api/cases` | 紧急标识：`understanding.urgent=true` 时显示“急” |
| GET | `/api/cases` | 工单标题：依次取 `work_order.title`、`understanding.demand`、`understanding.event`、`understanding.transcript`、`input.text` |
| GET | `/api/cases` | 工单创建时间：`created_at`，页面格式为 `MM/DD HH:mm` |
| GET | `/api/cases` | 工单列表顺序：按 `created_at` 倒序，默认显示前 8 条 |
| GET | `/api/cases` | 已分类工单数：存在 `classification.category_name` 或 `classification.category` 的工单数 |
| GET | `/api/cases` | 分类名称：优先取 `classification.category_name`，为空时取 `classification.category` |
| GET | `/api/cases` | 分类数量：按分类名称分组计数，页面显示数量最多的前 8 类 |
| GET | `/api/cases` | 未分类工单数：工单总数减去已分类工单数 |
| GET | `/api/cases/{case_id}` | 点击工单后加载该工单详情，并进入原工作流对应步骤 |
| GET | `/api/samples` | 点击“开始处理工单 →”进入工作流后，加载文本样例和录音样例 |
| GET | `/api/departments/rules` | 点击“打开数据管理 →”后，加载完整部门规则列表 |

> `GET /api/cases` 请求失败时，首页会显示前端内置的演示数据，并标记数据来源为“本地演示数据”。

## 数据管理页面接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/departments/rules` | 显示部门规则文件信息、规则数量和规则列表 |
| PUT | `/api/departments/rules/{code}` | 保存当前部门规则，并同步更新规则检索索引 |
| DELETE | `/api/departments/rules/{code}` | 删除当前部门规则，并同步更新规则检索索引 |
| POST | `/api/policies/uploads` | 上传政策文件，成功后返回上传凭据并弹出必填信息框 |
| POST | `/api/policies/uploads/{upload_id}/complete` | 提交文件名称、发布单位和所属分类，增量写入 `policy_docs` |
| DELETE | `/api/policies/uploads/{upload_id}` | 用户取消填写时删除尚未完成的暂存文件 |
| GET | `/api/policies/files` | 分页获取已完成入库的政策文件列表，不返回文件正文 |
| DELETE | `/api/policies/files/{upload_id}` | 删除已上传的政策文件、元数据和对应的 `policy_docs` 向量 |

### 政策文件上传流程

政策文件上传分为两个步骤：

1. 调用 `POST /api/policies/uploads` 上传原文件，支持 PDF、DOCX、TXT、Markdown、HTML 和 JSON，单个文件最大 20 MB。接口返回 `upload_id`、`filename` 和根据文件名生成的默认 `source_name`。
2. 调用 `POST /api/policies/uploads/{upload_id}/complete`，提交 `source_name`、`publisher` 和 `category_name`。后端保存元数据、拆分文件内容并增量写入 Chroma 的 `policy_docs` collection。

第二步尚未完成时，前端关闭信息填写弹窗会调用 `DELETE /api/policies/uploads/{upload_id}` 清理暂存文件。完成入库后如需删除，应调用 `/api/policies/files/{upload_id}`，两个 DELETE 接口的用途不同。

补充信息请求示例：

```json
{
  "source_name": "芜湖市房屋使用安全管理条例实施细则",
  "publisher": "芜湖市人民政府",
  "category_name": "城乡建设"
}
```

### 已上传政策文件列表

```http
GET /api/policies/files?page=1&page_size=20
```

| 查询参数 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- |
| `page` | `1` | 大于等于 1 | 页码 |
| `page_size` | `20` | 1～100 | 每页记录数 |

响应示例：

```json
{
  "items": [
    {
      "upload_id": "41502dd295d14e6c9cc2a53df84f3aa1",
      "filename": "芜湖市人民政府关于印发通知.docx",
      "source_name": "芜湖市房屋使用安全管理条例实施细则",
      "publisher": "芜湖市人民政府",
      "category_name": "城乡建设",
      "uploaded_at": "2026-09-04T21:36:55+08:00",
      "file_size": 84664
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

列表接口只扫描 `backend/data/raw/public_policies/uploads/{upload_id}` 中已经完成入库的文件，返回文件级元数据，不读取或返回政策正文。数据管理页面显示文件名称、原始文件名、发布单位、所属分类、上传日期和文件大小，不提供内容详情或下载入口。

### 删除已上传政策文件

```http
DELETE /api/policies/files/{upload_id}
```

成功响应：

```json
{
  "message": "政策文件已删除",
  "deleted_vectors": 6
}
```

删除接口仅作用于用户上传目录。后端先将目标目录移动到临时回收位置，再按向量 metadata 中的 `upload_id` 删除 `policy_docs` 记录；向量删除失败时会恢复文件目录。接口状态说明：

| 状态码 | 说明 |
| --- | --- |
| `200` | 文件、元数据和对应向量删除成功 |
| `404` | `upload_id` 格式不正确，或政策文件不存在/已经删除 |
| `500` | 文件或向量索引删除失败，前端保留当前列表项并显示错误信息 |

## 一、目录结构（单仓库）

```
12345Agent-New/            单仓库根（本仓库）
  backend/                 后端（FastAPI + SQLite）
    app/                   FastAPI 入口、配置、schemas、services、workflow、api、repositories
      data/loaders.py      数据加载器（分类目录、部门规则、历史工单等）
    data/                  分类目录(categories)、部门规则(departments)、mock 样例、
                           预处理产物(processed)、官方原始数据(raw)
    storage/cases.db       SQLite 库（自动创建，已 gitignore）
    scripts/prepare_dataset.py   官方 Excel -> work_orders.json 预处理
    scripts/inspect_chroma_index.py  查看 Chroma 向量库内容并导出
    tools/                 环境/连通性自检脚本（verify_env.py、test_deepseek.py）
    tests/                 pytest 测试（test_api / test_edge_cases / test_health）
    venv/                  后端虚拟环境（本机自带，已 gitignore）
    requirements.txt       后端依赖
    pytest.ini             pytest 配置
    .env / .env.example    LLM 配置（.env 不入库；.env.example 入库）
  frontend/                前端（React + TypeScript + Vite）
    src/                   源码（main.tsx / App.tsx / api.ts / components/ / styles.css）
      components/          Stepper（横向 Pipeline 轨道）+ 6 个阶段 Panel + CaseBar
    dist/                  构建产物（已提交仓库，由后端静态托管，无需 Node 即可演示）
    package.json / vite.config.ts / tsconfig.json / index.html
  docs/                    项目文档
    backend-architecture.md    后端架构设计文档
    backend-gap-list.md        后端能力缺口清单（前端改造配套，含 TODO 对照）
  activate_backend_venv.bat / .command    一键激活后端 venv（Win / macOS）
  activate_frontend_venv.bat / .command   前端开发环境说明（Win / macOS）
  run_server.bat           一键启动（位于上级目录，自动 cd backend 并拉起 uvicorn）
  README.md                本文件
  .gitignore
```

## 二、安装与运行（最简：一键启动）

直接双击上级目录的 **`run_server.bat`**，或本目录的 **`activate_backend_venv.bat`** 即可：自动进入 `backend/`、使用 `backend/venv` 虚拟环境安装依赖并启动后端（[http://127.0.0.1:8000）。](http://127.0.0.1:8000%EF%BC%89%E3%80%82)
前端 `frontend/dist` 已随仓库提交，单条 `uvicorn` 同时提供 API 与页面，**无需安装 Node.js 也能直接演示**。

手动方式：

### 1. 后端

先从仓库根目录进入 `backend/`，用标准库 `venv` 构建 Python 虚拟环境，激活后再安装依赖并启动：

```powershell
cd backend
# 1. 构建 Python 虚拟环境（仅在首次或环境缺失时执行）
python -m venv venv
# Windows 激活虚拟环境：
venv\Scripts\activate
# macOS / Linux 激活虚拟环境：
source venv/bin/activate
# 2. 安装依赖、检查环境、运行测试与启动服务
python -m pip install --upgrade pip setuptools wheel #安装基础工具
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ #安装依赖
```

初次构建依赖后执行：

```PowerShell
# 验证环境是否构建完成
Copy-Item .env.example .env
python verify_env.py
```

后端服务启动

```PowerShell
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

启动后访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

后端的 `.env`、依赖和运行命令均以 `backend/` 为工作目录。详细说明见 `backend/README.md`。

### 2. 前端

首次使用时从仓库根目录执行：

```powershell
cd frontend
npm install #前端依赖安装
npm run build #生产构建检查
```

前端服务启动

```PowerShell
cd frontend
npm run dev
```

启动后访问 Vite 输出的本地地址，通常是：

- `http://localhost:5173`

前端只允许保存 `VITE_API_BASE_URL` 等非敏感配置，真实模型密钥不得写入前端代码或前端环境变量。

访问：

- 页面（前端）：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- 引擎模式：[http://127.0.0.1:8000/api/meta](http://127.0.0.1:8000/api/meta)



###  3.  初始数据准备

1. 下载官方数据集：[12345赛题数据集-信件类别示例工单及录音.zip](https://pan.baidu.com/s/1ysOOYqmoAQTr_yJWQLXoyw?pwd=u9ca)，提取码：u9ca。

2. 打开官方数据集并解压，查看其中的 '信件类别示例工单及录音' 文件夹。
3. 将  '信件类别示例工单及录音' 文件夹 中的所有文件全部复制到项目的 项目的  `backend\data\raw\official_work_orders` 目录中。
4. 执行以下命令：

```powershell
cd backend
# Windows 激活环境
.\venv\Scripts\Activate.ps1

# macOS 激活环境
source venv/Script/activate

python scripts/prepare_dataset.py data/raw/official_work_orders
```



### 4. 数据安全

官方 Excel 与配套录音按类别放入 `backend/data/raw/official_work_orders/`。当前 `prepare_dataset.py` 只匹配并处理 Excel，不会打开、转写或分析录音。

真实密钥只写入 `backend/.env`，不得提交 Git。真实姓名、手机号、身份证号、详细地址、未经授权的录音和未脱敏工单不得进入公开仓库。



## 三、LLM 配置

复制 `backend/.env.example` 为 `backend/.env`，填入真实 Key（`config.py` 仅当 Key 非 `replace_me` 时启用大模型）：

```
# LLM Model - 推荐deepseek
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
APP_ENV=development

# 科大讯飞录音文件转写（可选，录音真实转写需要）
KDXF_ASR_APP_ID=replace_me
KDXF_ASR_ACCESS_KEY_ID=replace_me
KDXF_ASR_ACCESS_KEY_SECRET=replace_me
KDXF_ASR_BASE_URL=https://office-api-ist-dx.iflyaisol.com
KDXF_ASR_LANGUAGE=autodialect
KDXF_ASR_POLL_INTERVAL_SECONDS=4
KDXF_ASR_POLL_TIMEOUT_SECONDS=300
```

- 配置真实 Key 后，`/api/meta` 的 `engine_mode` 为 `llm`，理解/分类/工单/回复优先调用大模型，失败自动回退本地引擎。
- Key 为占位符 `replace_me` 或为空时，`engine_mode` 为 `local-engine`，全程使用确定性本地引擎，**无需联网即可演示**。
- 判别是否真用上大模型：看每个接口返回里的 `source` 字段——`"llm"` 为真调用，`"local-engine"` 为回退。
- 科大讯飞参数用于真实录音转写；配齐 `KDXF_ASR_APP_ID`、`KDXF_ASR_ACCESS_KEY_ID`、`KDXF_ASR_ACCESS_KEY_SECRET` 后，上传录音会优先调用讯飞 ASR。
- 科大讯飞参数保持 `replace_me` 或为空时，录音流程会继续使用样例精确匹配 / 模拟转写兜底，不影响文本工单演示。
- 所有真实密钥只写入 `backend/.env`，不要写入前端、截图、README 或提交到 Git。

## 四、核心接口

| 方法 | 路径                               | 说明                                                                                |
| ---- | ---------------------------------- | ----------------------------------------------------------------------------------- |
| POST | `/api/cases`                     | 创建案件（JSON`{text?,audio_filename?}` 或 `multipart/form-data` 带 `audio`） |
| GET  | `/api/cases`                     | 案件列表                                                                            |
| GET  | `/api/cases/{case_id}`           | 案件详情（含各阶段结果）                                                            |
| POST | `/api/cases/{case_id}/workorder` | 生成工单                                                                            |
| POST | `/api/cases/{case_id}/classify`  | 分类与承办单位推荐                                                                  |
| POST | `/api/cases/{case_id}/reply`     | 回复辅助                                                                            |
| POST | `/api/cases/{case_id}/confirm`   | 审核确认`{operator, note?}`                                                       |
| POST | `/api/cases/{case_id}/handling`  | 处理录入`{text}`                                                                  |
| GET  | `/api/departments/rules`         | 部门规则全量与文件信息                                                              |
| PUT  | `/api/departments/rules/{code}`  | 更新单条部门规则并重建规则检索索引                                                  |
| DELETE | `/api/departments/rules/{code}` | 删除单条部门规则并重建规则检索索引                                                  |
| GET  | `/api/samples`                   | 样例文本与样例录音（可按文件名精确转写）                                            |
| GET  | `/api/history?q=`                | 相似历史案例检索                                                                    |

## 五、快速全链路验证

```bash
curl -X POST http://127.0.0.1:8000/api/cases -H "Content-Type: application/json" \
  -d "{\"text\":\"南陵县某理发店没有公示服务价格，也没有在醒目位置悬挂营业执照，希望有关部门核查。\"}"
# 取返回 case_id，依次调用 /workorder /classify /reply /confirm
```

## 六、测试

```bash
cd 12345Agent-New\backend
venv\Scripts\python.exe -m pytest tests/ -q
```

## 七、查看 Chroma 向量库内容

`backend/scripts/inspect_chroma_index.py` 用于检查 Chroma 中各 collection 的记录内容、metadata 和检索结果。脚本会自动读取 `backend/app/rag/vectorstore.py` 中配置的 `CHROMA_DIR`，当前实际目录为 `backend/storage/chroma`，因此不需要额外传入 `--path`。

请在 `12345Agent-New/backend` 目录下执行。若尚未激活虚拟环境，可以直接使用项目自带 Python：

```powershell
cd 12345Agent-New\backend
venv\Scripts\python.exe scripts\inspect_chroma_index.py
```

### 1. 查看 collection 条数

不传参数时只列出各 collection 的记录数量，不会打印全部正文：

```powershell
venv\Scripts\python.exe scripts\inspect_chroma_index.py
```

当前项目预置的 collection 包括：

- `category_catalog`：分类目录
- `department_rules`：部门职责与规则
- `historical_cases`：历史工单
- `policy_docs`：政策文件

### 2. 查看指定 collection 的内容

使用 `-c` 或 `--collection` 指定 collection，使用 `--limit` 限制显示条数；`0` 表示不限制：

```powershell
# 查看分类目录前 10 条
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c category_catalog --limit 10

# 查看部门规则全部记录
venv\Scripts\python.exe scripts\inspect_chroma_index.py --collection department_rules
```

### 3. 按关键词过滤

`--grep` 会同时在 document 正文和 metadata 中进行不区分大小写的关键词匹配：

```powershell
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c department_rules --grep 住建
```

### 4. 执行语义检索

使用 `--query` 执行相似度检索，默认返回 3 条结果；可以通过 `--top-k` 调整返回数量：

```powershell
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c department_rules --query "路灯不亮找谁" --top-k 5
```

### 5. 导出为 Markdown、JSON 或 HTML

支持 `text`、`md`、`json`、`html` 四种输出格式。HTML 是单文件页面，打开后可以使用页面内搜索框查看记录：

```powershell
# 导出 Markdown
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c department_rules --format md -o out\department_rules.md

# 导出 JSON
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c category_catalog --format json -o out\category_catalog.json

# 导出带搜索框的 HTML 页面
venv\Scripts\python.exe scripts\inspect_chroma_index.py -c historical_cases --format html -o out\historical_cases.html
```

说明：脚本一次只查看一个 collection 的详细内容；不传 `--collection` 时只显示所有 collection 的条数。若要查看全部 collection 的正文，需要分别指定 `-c` 执行，或分别导出为 HTML/JSON 文件。

## 八、说明与免责

- 部门职责（`backend/data/departments/department_rules.json`）与分类目录为**示例性归纳**，非现行权威权责，仅用于演示；正式版本以主办方提供目录为准。
- 系统**仅提供辅助建议**，最终由工作人员确认（confirm 写 audit_log）。
- 可选增强（faster-whisper / qdrant 向量检索 / RAG 多轮追问）未强制，按需安装。
- 官方原始数据集（`backend/data/raw/official_work_orders/`）仅保存在本机，不入库；演示样例 `work_orders.json` 已随仓库提供。

---

## 九、首次接手者详细运行指南（补充）

本章面向第一次拿到项目、希望独立完成环境准备、启动、联调和验收的开发者。前面章节保留了项目原有说明；若其中出现旧目录名（如 `12345Agent-New`），请以当前项目目录 `12345agent-3` 为准。

### 9.1 推荐环境与前置条件

#### 推荐环境

| 项目 | 推荐配置 | 是否必需 | 说明 |
| --- | --- | --- | --- |
| 操作系统 | Windows 10/11；macOS 13 及以上 | 是 | 当前教学环境以 Windows 为主，代码同时提供 macOS 激活脚本 |
| Python | Python 3.11 | 是 | 建议固定使用项目内 `backend/venv`，避免与系统 Python 或 Conda 混用 |
| Node.js | Node.js 20 及以上，教学环境可使用 Node.js 24 | 修改前端时必需 | 只使用已经构建好的 `frontend/dist` 时可不单独启动 Node |
| npm | 随 Node.js 安装的稳定版本 | 修改前端时必需 | 用于安装前端依赖、启动 Vite 和构建 `dist` |
| Git | 当前稳定版本 | 建议 | 用于获取代码和查看修改 |
| 浏览器 | Chrome、Edge 或其他现代浏览器 | 是 | 用于访问页面、Swagger 和开发者工具 |
| 内存 | 至少 8 GB，推荐 16 GB | 建议 | 首次加载本地 Embedding 模型时占用较高 |
| 磁盘 | 至少预留 10 GB | 建议 | Python 依赖、Node 依赖、本地模型和向量索引会占用空间 |
| 网络 | 安装依赖时需要 | 视情况 | 本地引擎可离线演示；真实 LLM、ASR 和首次下载模型需要联网 |

#### 启动前确认

1. 本机的 8000 端口可供 FastAPI 使用，5173 端口可供 Vite 开发服务器使用。
2. 项目目录中至少包含 `backend/`、`frontend/` 和本 README。
3. 不需要单独安装 MySQL、PostgreSQL 或独立向量数据库服务。案件数据使用 SQLite，RAG 使用本地 Chroma。
4. 真实 API Key 只写入 `backend/.env`，不要写入前端、README、截图或提交记录。
5. 首次接手时不要假设 `frontend/dist` 一定存在。若不存在，应先完成前端构建。
6. 如项目自带 `backend/venv`，仍应先执行环境检查；如果该环境与当前系统不兼容，应删除后重新创建本机环境。

### 9.2 首次安装：Windows 推荐步骤

以下命令均从 `12345agent-3` 项目根目录开始。

#### 第 1 步：准备后端虚拟环境

```powershell
cd backend

# 仅当 venv 不存在或不可用时创建
python -m venv venv

# 不依赖终端激活状态，直接使用项目 Python 安装依赖
.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果 `python` 命令不可用，请先安装 Python 3.11，并重新打开终端。不要把依赖装到一个 Python，再使用另一个 Python 启动项目。

#### 第 2 步：准备环境变量

```powershell
# 仅当 .env 不存在时执行，已有 .env 时不要覆盖
Copy-Item .env.example .env
```

不配置真实模型 Key 时，保留占位值即可，系统会进入 `local-engine` 模式。修改 `.env` 后需要重新启动后端。

#### 第 3 步：检查后端依赖

```powershell
.\venv\Scripts\python.exe tools\verify_env.py
.\venv\Scripts\python.exe -m pip check
```

预期结果：

- `verify_env.py` 最后一行显示 `Environment check passed.`；
- `pip check` 显示 `No broken requirements found.`。

如果某个模块导入失败，先确认命令中的 Python 路径确实指向 `backend\venv\Scripts\python.exe`，再重新安装对应依赖。

#### 第 4 步：检查或构建 RAG 索引

```powershell
.\venv\Scripts\python.exe scripts\inspect_chroma_index.py
```

正常情况下会看到以下 collection 及其记录数量：

- `category_catalog`
- `department_rules`
- `historical_cases`
- `policy_docs`

如果前三个 collection 不存在或数量为 0，可执行：

```powershell
.\venv\Scripts\python.exe scripts\build_chroma_index.py --source official
```

如果需要同时重建项目内政策资料：

```powershell
.\venv\Scripts\python.exe scripts\build_chroma_index.py --source all
```

首次加载 Embedding 模型可能需要较长时间。项目会优先使用 `backend/storage/models/bge-small-zh-v1.5`；本地模型不存在时，才会尝试使用远程模型名称。

#### 第 5 步：安装并构建前端

回到项目根目录后执行：

```powershell
cd ..\frontend
npm install
npm run build
```

构建成功后应生成 `frontend/dist/index.html`。如果仓库中已经有完整的 `node_modules`，仍建议至少执行一次 `npm run build`，确认当前源码可以正常编译。

#### 第 6 步：运行测试

```powershell
cd ..\backend
.\venv\Scripts\python.exe -m pytest tests -q
```

测试应覆盖健康检查、案件全流程、边界场景、LangGraph、RAG、政策文件和部门规则接口。测试数量会随项目更新变化，应以“全部通过”为判断标准，不要只对照历史文档中的固定数量。

#### 第 7 步：启动后端

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动成功后访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/health`
- 接口文档：`http://127.0.0.1:8000/docs`
- 引擎信息：`http://127.0.0.1:8000/api/meta`

如果首页只显示“前端未构建”，说明 `frontend/dist` 不存在或构建失败，请回到第 5 步。

### 9.3 前后端启动顺序

本项目支持两种运行方式。

#### 方式 A：单服务演示模式（推荐用于 Workshop）

1. 先在 `frontend/` 执行 `npm run build`；
2. 再从 `backend/` 启动 FastAPI；
3. 浏览器访问 `http://127.0.0.1:8000/`。

此时 FastAPI 同时提供 API 和 `frontend/dist` 中的静态页面。页面与接口同源，不需要单独处理开发代理。

#### 方式 B：前后端分离开发模式

先启动后端：

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

再打开第二个终端启动前端：

```powershell
cd frontend
npm run dev
```

浏览器访问 `http://127.0.0.1:5173/` 或终端显示的 Vite 地址。

当前前端的 API 地址使用相对路径 `/api`，`vite.config.ts` 会把开发环境中的 `/api` 请求代理到 `http://127.0.0.1:8000`。因此推荐先启动后端，再启动前端。

如果后端改用 8001 等其他端口，需要同步修改 `frontend/vite.config.ts` 中的代理目标并重新启动 Vite。

### 9.4 环境变量用途

配置文件位于 `backend/.env`。应用从当前工作目录读取该文件，因此后端命令应在 `backend/` 目录中执行。

| 变量 | 用途 | 不配置时的行为 |
| --- | --- | --- |
| `LLM_API_KEY` | 大模型服务密钥 | 为空或为 `replace_me` 时使用本地引擎 |
| `LLM_BASE_URL` | OpenAI 兼容接口地址 | 没有真实 Key 时不会调用 |
| `LLM_MODEL` | 聊天模型名称 | 没有真实 Key 时不会调用 |
| `EMBEDDING_MODEL` | RAG 使用的 Embedding 模型路径或名称 | 优先查找项目内 `storage/models/bge-small-zh-v1.5`，否则使用默认远程模型名 |
| `APP_ENV` | 当前运行环境标识 | 默认 `development`；当前主要用于配置区分 |
| `WORKFLOW_ENGINE` | 工作流实现，可选 `langgraph` 或 `legacy` | 推荐 `langgraph`；非法值会回退到 `legacy` |
| `KDXF_ASR_APP_ID` | 科大讯飞应用标识 | 未完整配置时不调用真实讯飞 ASR |
| `KDXF_ASR_ACCESS_KEY_ID` | 科大讯飞访问凭据 | 同上 |
| `KDXF_ASR_ACCESS_KEY_SECRET` | 科大讯飞签名密钥 | 同上 |
| `KDXF_ASR_BASE_URL` | 科大讯飞录音转写服务地址 | 使用代码中的默认地址 |
| `KDXF_ASR_LANGUAGE` | 录音语言或方言配置 | 默认 `autodialect` |
| `KDXF_ASR_POLL_INTERVAL_SECONDS` | 查询录音转写结果的间隔 | 默认 5 秒 |
| `KDXF_ASR_POLL_TIMEOUT_SECONDS` | 等待录音转写的最长时间 | 默认 900 秒 |

配置后可通过以下接口确认状态：

```text
GET /api/meta
```

重点查看：

- `engine_mode=llm`：已识别到真实 LLM Key；
- `engine_mode=local-engine`：未配置真实 Key；
- `workflow_engine=langgraph`：当前使用 LangGraph；
- `workflow_engine=legacy`：当前使用旧版串行工作流。

`engine_mode=llm` 只表示配置被识别。要确认本次调用是否真的成功使用模型，还应查看各阶段结果中的 `source`。模型调用失败后会自动回退，并显示 `source=local-engine`。

### 9.5 当前已完成和未完成功能

#### 已完成

| 功能 | 当前状态 |
| --- | --- |
| 文本案件创建与诉求理解 | 已完成，支持 LLM 和本地规则回退 |
| 录音案件创建 | 已完成样例文件名匹配、科大讯飞 ASR 接入和模拟转写兜底 |
| 标准化工单生成 | 已完成，结果包含标题、摘要、正文和关键要素 |
| 事项分类和承办单位推荐 | 已完成，支持分类目录、部门职责和历史案例检索 |
| 回复辅助 | 已完成受理提示、办理建议、预回复和回访话术生成 |
| 人工确认与审计日志 | 已完成 `confirm` 接口和 `audit_log` 记录 |
| LangGraph 工作流 | 已完成主要节点、条件分支、质量标记、流程轨迹和 SQLite checkpoint |
| Chroma RAG | 已完成四类 collection、MMR 检索和元数据过滤 |
| 部门规则管理 | 已完成查询、修改、删除和索引同步 |
| 政策文件管理 | 已完成上传、补充元数据、增量入库、列表和删除 |
| 案件持久化 | 已完成 SQLite 保存、案件列表和案件详情回看 |
| 前端页面 | 已完成首页、工单工作台和数据管理页面 |
| 自动测试 | 已覆盖核心 API、边界案例、LangGraph、RAG、政策文件和部门规则 |

#### 当前限制和待完善项

| 项目 | 当前限制 |
| --- | --- |
| 诉求要素人工修改 | 页面中的修改目前只保存在前端当前会话，没有回写后端 |
| 预回复人工修改 | 页面中的编辑目前只保存在前端当前会话，确认时不会保存修改后的正文 |
| 办理结果联动 | `POST /handling` 当前只把办理文字写入 `audit_log`；回复生成尚未读取该办理结果 |
| 真实派单 | 当前只生成分类和承办单位建议，没有连接正式 12345 派单系统 |
| 用户与权限 | 当前没有登录、角色、权限控制和多用户隔离 |
| 人工审核流程 | 当前通过页面确认、状态字段和审计记录实现，尚未接入外部审批系统 |
| ASR 可靠性 | 未配置或调用失败时会使用模拟转写；必须检查 `transcript_source` |
| 部门职责权威性 | 当前部门规则是演示资料，不能当作正式权责依据 |
| 政策文件查看 | 当前支持上传、列表和删除，不提供在线正文预览或下载入口 |
| 生产部署 | 当前定位为本地 Demo，尚未完成生产级鉴权、日志、监控、备份和高并发设计 |

首次接手者应先完成现有闭环，再根据任务选择待完善项。不要在 README 或演示中把上述限制描述成已经完成的生产能力。

### 9.6 接口状态与调用顺序

#### 基础状态接口

| 方法 | 路径 | 状态 | 用途 |
| --- | --- | --- | --- |
| GET | `/health` | 已实现 | 检查后端是否运行、是否识别到 LLM Key |
| GET | `/api/meta` | 已实现 | 查看模型模式和工作流模式 |
| GET | `/docs` | 已实现 | 使用 Swagger 查看和调用全部接口 |

#### 案件主流程接口

| 建议顺序 | 方法 | 路径 | 状态与说明 |
| --- | --- | --- | --- |
| 1 | POST | `/api/cases` | 已实现；提交文本或录音，创建案件并完成诉求理解 |
| 2 | POST | `/api/cases/{case_id}/classify` | 已实现；分类并推荐承办单位 |
| 3 | POST | `/api/cases/{case_id}/workorder` | 已实现；生成标准化工单 |
| 4 | POST | `/api/cases/{case_id}/handling` | 已实现但能力有限；当前只记录办理文字 |
| 5 | POST | `/api/cases/{case_id}/reply` | 已实现；生成回复辅助内容，但暂未使用 handling 文本 |
| 6 | POST | `/api/cases/{case_id}/confirm` | 已实现；写入操作人、备注和确认状态 |
| 查询 | GET | `/api/cases/{case_id}` | 已实现；返回该案件的完整持久化状态 |
| 查询 | GET | `/api/cases` | 已实现；返回案件列表 |

分阶段接口会通过同一个 `case_id` 串联。调用不存在的 `case_id` 会返回 404；缺少必填输入、操作人或处理文字时通常返回 400。

#### 数据与检索接口

| 方法 | 路径 | 状态与说明 |
| --- | --- | --- |
| GET | `/api/samples` | 已实现；返回文本样例和录音样例 |
| GET | `/api/history?q=关键词` | 已实现；返回相似历史案例 |
| GET | `/api/departments/rules` | 已实现；获取部门规则 |
| PUT | `/api/departments/rules/{code}` | 已实现；更新规则并同步索引 |
| DELETE | `/api/departments/rules/{code}` | 已实现；删除规则并同步索引 |
| POST | `/api/policies/uploads` | 已实现；上传政策原文件，成功返回 upload_id |
| POST | `/api/policies/uploads/{upload_id}/complete` | 已实现；填写元数据并完成入库 |
| DELETE | `/api/policies/uploads/{upload_id}` | 已实现；取消未完成的上传 |
| GET | `/api/policies/files` | 已实现；分页列出已入库政策文件 |
| DELETE | `/api/policies/files/{upload_id}` | 已实现；删除已入库文件及对应向量 |

### 9.7 前后端联调方法

#### 开发模式的数据流

```text
浏览器 http://127.0.0.1:5173
        ↓ 请求 /api/*
Vite 开发代理
        ↓ 转发到
FastAPI http://127.0.0.1:8000
        ↓
SQLite / Chroma / 本地文件 / 可选外部模型服务
```

#### 联调检查顺序

1. 直接访问 `http://127.0.0.1:8000/health`，确认后端正常；
2. 直接访问 `http://127.0.0.1:8000/api/meta`，确认模型和工作流模式；
3. 在 `http://127.0.0.1:8000/docs` 中手动调用 `POST /api/cases`；
4. 确认 Swagger 可以成功后，再打开 5173 前端页面；
5. 在浏览器开发者工具的 Network 面板中查看 `/api/*` 请求；
6. 若前端失败但 Swagger 成功，重点检查 Vite 代理和前端状态；
7. 若 Swagger 也失败，重点查看 FastAPI 终端报错、输入参数和数据文件。

当前后端只允许本机的 `http://127.0.0.1:5173` 和 `http://localhost:5173` 跨域访问。使用其他域名、局域网 IP 或端口时，需要同步调整后端 CORS 配置。

### 9.8 测试和运行验证

#### 环境测试

```powershell
cd backend
.\venv\Scripts\python.exe tools\verify_env.py
.\venv\Scripts\python.exe -m pip check
```

#### 后端全部测试

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

#### 分模块测试

```powershell
# 核心 API 和全链路
.\venv\Scripts\python.exe -m pytest tests\test_api.py -q

# 信息缺失、紧急事件、重复诉求等边界情况
.\venv\Scripts\python.exe -m pytest tests\test_edge_cases.py -q

# LangGraph 状态与分支
.\venv\Scripts\python.exe -m pytest tests\test_langgraph_workflow.py -q

# Chroma RAG
.\venv\Scripts\python.exe -m pytest tests\test_rag_index.py -q

# 政策文件
.\venv\Scripts\python.exe -m pytest tests\test_policy_uploads.py -q

# 首页、SPA 路由与部门规则
.\venv\Scripts\python.exe -m pytest tests\test_homepage_capabilities.py -q
```

#### 前端构建测试

```powershell
cd ..\frontend
npm run build
```

TypeScript 检查和 Vite 构建都成功，并生成 `frontend/dist/index.html`，才算通过。

#### 模型连通性测试

仅在 `backend/.env` 已配置真实 LLM Key 时执行：

```powershell
cd ..\backend
.\venv\Scripts\python.exe tools\test_deepseek.py
```

如果使用其他 OpenAI 兼容服务，也可以使用该脚本，但必须确保 `LLM_BASE_URL` 和 `LLM_MODEL` 与服务商要求一致。

#### PowerShell 手工全链路验证

先保持后端运行，再打开另一个 PowerShell：

```powershell
$base = "http://127.0.0.1:8000"

$body = @{
  text = "南陵县某理发店没有公示服务价格，也没有在醒目位置悬挂营业执照，希望有关部门核查。"
} | ConvertTo-Json

$case = Invoke-RestMethod -Method Post -Uri "$base/api/cases" -ContentType "application/json" -Body $body
$caseId = $case.case_id

Invoke-RestMethod -Method Post -Uri "$base/api/cases/$caseId/classify"
Invoke-RestMethod -Method Post -Uri "$base/api/cases/$caseId/workorder"
Invoke-RestMethod -Method Post -Uri "$base/api/cases/$caseId/reply"

$confirmBody = @{
  operator = "workshop-user"
  note = "本地验收通过"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "$base/api/cases/$caseId/confirm" -ContentType "application/json" -Body $confirmBody
Invoke-RestMethod -Method Get -Uri "$base/api/cases/$caseId"
```

最终详情应包含理解、分类、工单、回复、`confirmed=true` 和审核记录。

### 9.9 常见错误处理

| 现象 | 常见原因 | 处理方法 |
| --- | --- | --- |
| `python` 或 `python3` 找不到 | Python 未安装或终端未刷新 PATH | 安装 Python 3.11，关闭并重新打开终端 |
| 已安装依赖但仍提示 `ModuleNotFoundError` | 安装和运行使用了不同 Python | 统一使用 `backend/venv` 中的 Python执行安装和启动 |
| `.env` 已填写但仍显示 `local-engine` | 启动目录错误、Key 仍为占位值或服务未重启 | 从 `backend/` 启动；检查变量；重启后端 |
| 模型返回 401 | Key、Base URL 或模型名错误 | 核对服务商配置，不要把完整 Key 放入截图 |
| 模型返回 429 | 额度、频率或并发限制 | 检查账户额度，降低调用频率，稍后重试 |
| 模型请求超时 | 网络、代理、防火墙或服务不可用 | 先检查网络；课堂演示可继续使用本地引擎 |
| 首页显示“前端未构建” | `frontend/dist/index.html` 不存在 | 在 `frontend/` 执行 `npm install` 和 `npm run build` |
| 修改前端后 8000 页面没变化 | 只改了源码，没有重建 `dist` | 重新执行 `npm run build`，再强制刷新浏览器 |
| 5173 页面能打开但接口失败 | 后端未启动、代理端口不一致或 CORS 配置不匹配 | 先检查 8000 的 `/health`，再检查 Vite 代理和 Network 面板 |
| 8000 端口被占用 | 旧服务或其他程序正在使用 | 关闭旧服务，或换端口并同步修改前端代理 |
| 首页显示“本地演示数据” | `GET /api/cases` 调用失败 | 检查后端终端和浏览器 Network，不要把演示数据当成真实数据库结果 |
| RAG 没有检索结果 | collection 为空、Embedding 模型不可用或查询过于模糊 | 查看 collection 数量；检查模型路径；重新建索引；改写查询 |
| 首次 RAG 调用很慢 | 正在加载本地模型或首次创建索引 | 等待模型加载完成；不要重复点击；观察后端日志 |
| Windows 出现 Torch、Chroma 或 DLL 错误 | Python、Torch、运行库或架构不兼容 | 使用 Python 3.11 项目环境；安装系统 Visual C++ 运行库；优先使用 CPU |
| 录音结果显示 `simulated` | 未配置 ASR、鉴权失败、网络失败或文件不匹配 | 检查讯飞配置和后端日志；演示时明确说明这是模拟转写 |
| 政策文件上传后检索不到 | 只上传了文件，未提交补充信息完成入库 | 完成 source_name、publisher、category_name 三项信息 |
| `case_id 不存在` | 使用了旧 ID、数据库被替换或启动了另一个项目副本 | 从当前首页重新复制 case_id，确认使用同一个 `storage/cases.db` |
| pytest 在收尾阶段报第三方插件错误 | 全局 pytest 插件影响项目 | 使用项目虚拟环境；项目 `pytest.ini` 已禁用已知的 hypothesis 插件 |

### 9.10 首次接手验收清单

#### A. 环境验收

- [ ] 后端实际使用 Python 3.11 和项目 `backend/venv`
- [ ] `tools/verify_env.py` 通过
- [ ] `pip check` 无依赖冲突
- [ ] `npm run build` 成功
- [ ] `frontend/dist/index.html` 已生成

#### B. 服务验收

- [ ] `GET /health` 返回 `status=ok`
- [ ] `GET /api/meta` 返回正确的 `engine_mode` 和 `workflow_engine`
- [ ] `/docs` 可以打开
- [ ] 首页、`/pipeline` 和 `/data` 可直接访问并刷新
- [ ] 后端重启后，已创建案件仍可查询

#### C. 主流程验收

- [ ] 文本诉求可以创建案件并返回 `case_id`
- [ ] 理解结果包含原文、事件、诉求、缺失项和紧急标识
- [ ] 分类结果包含类别、候选单位、理由和人工复核提示
- [ ] 工单包含标题、摘要、正文和关键要素
- [ ] 回复包含受理提示、办理建议、预回复和回访话术
- [ ] 确认操作写入操作人、备注和 `audit_log`
- [ ] 案件详情能按同一 `case_id` 回看各阶段结果

#### D. 异常场景验收

- [ ] 信息不完整的样例能标记缺失信息
- [ ] 燃气泄漏等紧急样例能标记紧急风险
- [ ] 低置信度或职责交叉时能提示人工复核
- [ ] 未配置 LLM 时仍可通过本地引擎跑通
- [ ] 未配置 ASR 时能明确标记样例匹配或模拟转写来源
- [ ] RAG 无结果时主流程不会直接崩溃

#### E. 数据与安全验收

- [ ] 四个 Chroma collection 的数量可查看
- [ ] 部门规则修改后索引同步成功
- [ ] 政策文件可以完成“上传—补充信息—入库—列表—删除”
- [ ] `.env`、真实 Key、未脱敏工单和录音未进入公开提交材料
- [ ] 演示中明确说明部门推荐、回复和政策内容需要人工确认

#### F. 测试验收

- [ ] 后端全部 pytest 用例通过
- [ ] 前端 TypeScript 和生产构建通过
- [ ] 至少一条正常样例完成端到端回放
- [ ] 至少一条信息缺失或紧急样例完成回放
- [ ] 已阅读并知晓“9.5 当前限制和待完善项”

完成以上检查后，首次接手者应能够独立启动项目、判断当前运行模式、完成基础联调，并区分已实现的 Demo 能力与仍需继续开发的功能。
