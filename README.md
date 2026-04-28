# 股票筛选器

A 股个人选股工具，支持按基本面和技术面指标多条件筛选。

## 快速开始

### 后端
```bash
cd backend
pip install -r ../requirements.txt
python seed_data.py          # 从 akshare 拉取数据（首次约 60 秒）
uvicorn main:app --reload    # API 运行在 http://localhost:8000
```

### 前端
```bash
cd frontend
npm install
npm run dev                  # 界面运行在 http://localhost:5173
```

## 技术栈
- 后端：Python 3.11+, FastAPI, SQLAlchemy, pandas, akshare
- 前端：Vue 3 (Composition API), TypeScript, Vite
- 数据库：SQLite

## 功能
- 多条件选股（PE、PB、ROE、市值、股息率、换手率等）
- 结果表格支持排序和分页
- 股票详情抽屉
- 策略模板保存/加载
- CSV 导出
