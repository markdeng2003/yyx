# ETF Volume Profile 项目骨架

本仓库包含一个最小可运行的前后端项目结构：

- `backend/`：Python + FastAPI 服务
- `frontend/`：Streamlit 页面

## 目录结构

```text
.
├── backend
│   ├── app
│   │   └── main.py
│   └── requirements.txt
├── frontend
│   ├── app.py
│   └── requirements.txt
└── README.md
```

## 后端运行方式

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查接口：`GET http://127.0.0.1:8000/health`

## 前端运行方式

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

页面包含：

- ETF 代码输入
- 周期选择（`1m/5m/15m/30m/60m/1d`）
- 日期范围输入
- volume profile 图表预留区域
