# 股票筛选器

A 股个人选股工具，支持按基本面和技术面指标多条件筛选，集成 AI 智能分析和策略管理。

## 环境准备

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端 API 与数据抓取 |
| Node.js | 18+ | 前端构建与开发 |
| npm | 9+ | 随 Node.js 发行 |

### 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 安装前端依赖

```bash
cd frontend
npm install
```

## 快速开始

### 1. 启动后端

```bash
cd backend
uvicorn main:app --reload
```

API 运行在 `http://localhost:8000`。首次启动时数据库为空，会自动从新浪财经拉取全量 A 股数据（约 60 秒）。也可手动执行：

```bash
python seed_data.py
```

### 2. 启动前端

```bash
cd frontend
npm run dev
```

界面运行在 `http://localhost:5173`，开发模式下自动代理 `/api` 到后端。

### 3. 配置 AI（可选）

如需使用「AI 选股」功能，在页面上点击右上角 ⚙ 按钮配置：

- **API URL**：OpenAI 兼容接口地址（默认 `https://api.openai.com/v1`）
- **Model**：模型名称（如 `gpt-4o`、`deepseek-chat` 等）
- **API Key**：你的 API 密钥

配置保存在 `data/ai_config.json`，已加入 `.gitignore`，不会提交到仓库。

## 项目结构

```
stock-screener/
├── backend/
│   ├── main.py              FastAPI 入口，注册路由与生命周期
│   ├── database.py          SQLAlchemy 引擎与初始化
│   ├── models.py            ORM 模型（StockBasic, StockDaily, StockConcept）
│   ├── seed_data.py         数据播种：拉取 → 清洗 → 入库
│   ├── routers/
│   │   ├── stocks.py        股票筛选、详情、K 线、分时、板块排名、涨跌停板
│   │   ├── strategies.py    策略保存/加载 API
│   │   ├── agent.py         AI 对话接口（SSE 流式输出）
│   │   └── ai_config.py     AI 配置读写
│   └── services/
│       ├── data_fetcher.py  新浪财经数据抓取（行情/财务/K 线/分时）
│       ├── screener.py      筛选引擎：DataFrame 内存过滤与分页
│       ├── indicator.py     技术指标计算（MA/MACD/RSI/KDJ/布林带）
│       └── agent.py         AI Agent 核心（LLM + function calling）
├── frontend/
│   ├── src/
│   │   ├── App.vue          根组件：Tab 导航、全局状态、主题切换
│   │   ├── api/index.ts     HTTP 客户端（fetch 封装 + 类型定义）
│   │   ├── types/index.ts   TypeScript 接口
│   │   ├── composables/     组合式函数（useWatchlist）
│   │   └── components/
│   │       ├── Sidebar.vue          筛选面板（关键词/市场/概念/基本面/技术面）
│   │       ├── StockTable.vue       股票列表（排序/分页/自选切换/CSV 导出）
│   │       ├── StockDetail.vue      股票详情抽屉（分时图/K 线/MACD/日K表）
│   │       ├── AgentChat.vue        AI 对话（Markdown 渲染/SSE 流式/记忆管理）
│   │       ├── AiSettings.vue       AI 配置面板
│   │       ├── StrategyDashboard.vue 策略仪表盘（交集分析/多策略概览）
│   │       ├── StrategySave.vue     策略保存/加载
│   │       ├── SectorRanking.vue    板块排名
│   │       ├── LimitStats.vue       涨跌停板统计
│   │       ├── FilterGroup.vue      区间筛选组件
│   │       ├── MarketFilter.vue     市场板块选择器
│   │       └── ...
│   └── vite.config.ts       Vite 配置（含 API 代理）
├── data/                    运行时数据（SQLite、策略 JSON、AI 配置）
│   ├── stocks.db            SQLite 数据库
│   ├── strategies.json      自定义策略持久化
│   └── ai_config.json       AI 模型配置（不入库）
└── requirements.txt         Python 依赖
```

## 功能

### 股票筛选

- 多条件组合筛选：PE (TTM)、PB、ROE、市值、股息率、营收增长率、换手率、涨跌幅、量比
- 市场板块过滤：沪深A股、创业板、科创板、北交所
- 概念板块过滤：搜索 + 复选，数据来自同花顺概念板块
- 关键字搜索：股票名称、代码
- 排除 ST 股票（默认关闭，手动开启）
- 自选股模式：收藏股票，导航栏「自选」标签独立展示
- 表格排序：点击列标题 → 升序 → 降序 → 取消
- 分页浏览，CSV 数据导出

### 股票详情（侧边抽屉）

- 基本信息：代码、名称、市场、行业、上市日期、PE、PB、ROE、市值
- 分时图：当日价格线 + 均价线 + 成交量柱，含昨收参考线
- K 线蜡烛图：日K / 周K / 月K 切换，MA5 / MA20 / MA60 均线 + 成交量
- MACD 技术指标图：DIF / DEA / MACD 柱
- 最近 120 个交易日 OHLCV 数据表

### 策略管理

- 6 个内置策略模板：高ROE成长股、低估值蓝筹、均线多头排列、新高附近、放量突破、低位高换手
- 自定义策略：保存 / 加载 / 删除（内置策略不可删除）
- 快捷策略栏：股票筛选页顶部标签一键应用
- 策略仪表盘：
  - 多策略运行概览（匹配股票数 + Top 5）
  - 策略交集分析（多条件交叉筛选）
  - 创建策略对话框

### 板块排名

- 行业板块按涨跌幅排序
- 展示换手率、领涨股及涨幅、板块成分股数量
- 点击板块查看成分股列表

### 涨跌停板

- 涨停板统计：连板数、封单量、封板时间、所属行业
- 跌停板统计
- 精确限价计算：从涨跌幅反推交易所调整前收盘价，精确到分
- 点击股票弹出详情
- 数据来源：新浪财经 + 东方财富封单数据

### AI 智能选股

- 自然语言股票分析：「分析贵州茅台」生成完整技术分析报告
- 多周期技术指标：日/周/月K 的 MA、MACD、RSI、KDJ、布林带
- 股票筛选：「找 PE<15、ROE>20%、MACD 金叉的股票」
- 多股对比：同时分析多只股票并排比较
- 市场全景：涨跌停统计、板块排名
- SSE 流式输出，支持中途停止
- 对话记忆系统：
  - 多对话管理（新建/切换/删除）
  - 上下文窗口 5 条消息，超出自动增量摘要压缩（100 字中文摘要）
  - localStorage 持久化存储
- Markdown 渲染：表格、列表、标题、加粗等
- 支持 OpenAI 兼容 API（可自行配置 Key、URL、模型）

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.11+, FastAPI |
| 数据库 | SQLite + SQLAlchemy ORM |
| 数据处理 | pandas |
| 数据来源 | 新浪财经 API（行情/指标），akshare（K线/分红/概念），东方财富（封单） |
| LLM | OpenAI 兼容 API（GPT-4o / DeepSeek 等） |
| 前端框架 | Vue 3 (Composition API), TypeScript |
| 构建工具 | Vite 5 |
| 图表 | lightweight-charts 5 |
| Markdown | markdown-it |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stocks` | 股票筛选（支持全部筛选参数） |
| GET | `/api/stocks/{code}` | 股票详情（基本信息 + 日K数据） |
| GET | `/api/stocks/{code}/intraday` | 分时数据（1分钟线） |
| GET | `/api/stocks/{code}/kline?period=daily\|weekly\|monthly` | K 线数据 |
| GET | `/api/markets` | 市场板块列表 |
| GET | `/api/concepts` | 概念板块列表 |
| GET | `/api/sectors` | 行业板块排名 |
| GET | `/api/limit-stats` | 涨跌停板统计 |
| GET | `/api/strategies` | 策略列表 |
| POST | `/api/strategies` | 保存/覆盖策略 |
| POST | `/api/refresh` | 手动刷新数据 |
| GET | `/api/refresh/status` | 刷新状态查询 |
| GET | `/api/ai-config` | 获取 AI 配置（不含 Key） |
| POST | `/api/ai-config` | 保存 AI 配置 |
| POST | `/api/agent/chat` | AI 对话（SSE 流式） |

## 架构说明

- **筛选引擎**：绕过 ORM，使用原生 SQL 联表查询后加载到 pandas DataFrame，所有过滤、排序在内存中完成。A 股全量约 5500 只，每次请求加载全量后在内存中计算，性能足够。
- **数据播种**：首次启动检测 `stock_basic` 表为空时自动拉取全量数据。支持手动触发 `POST /api/refresh`。刷新时加锁防止并发。
- **交易日检测**：通过分时数据格式自动判断是否真实交易日（交易日返回 `HH:MM`，节假日返回完整时间戳 `YYYY-MM-DD HH:MM:SS`），避免在休市日标注错误的交易日期。
- **涨跌停计算**：从涨跌幅反推交易所除权调整后的前收盘价，精确计算涨停价/跌停价（四舍五入到分），比百分比阈值法更准确。
- **前端无路由**：单页应用，通过 `activeTab` 状态切换视图，`sessionStorage` 保持标签页状态。
