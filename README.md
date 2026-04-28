# 股票筛选器

A 股个人选股工具，支持按基本面和技术面指标多条件筛选。

## 快速开始

### 后端
```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload    # API 运行在 http://localhost:8000
```
首次启动时自动从新浪财经拉取数据（约 60 秒），也可手动执行 `python seed_data.py`。

### 前端
```bash
cd frontend
npm install
npm run dev                  # 界面运行在 http://localhost:5173
```

## 技术栈
- 后端：Python 3.11+, FastAPI, SQLAlchemy, pandas, akshare (K线), 新浪财经 API (选股指标)
- 前端：Vue 3 (Composition API), TypeScript, Vite
- 数据库：SQLite

## 功能
- 多条件选股（PE、PB、ROE、市值、股息率、换手率等）
- 关键字搜索（股票名称或代码）
- 结果表格支持排序（升序/降序/取消）和分页
- 股票详情抽屉（K 线蜡烛图 + 日 K 线数据表）
- 一键刷新数据
- 明暗主题切换
- 策略模板保存/加载
- CSV 导出
