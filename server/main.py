import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

try:
    from .api import router
except ImportError:
    from api import router

app = FastAPI(title="中医药知识图谱管理模块 (任务2)", version="1.0.0",
              description="实体录入 / 关系维护 / 批量导入 / 图谱检索 / 可视化数据接口")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 组内联调放开；答辩前可收紧到任务5的前端域名
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _ensure_admin():
    try:
        from server.bootstrap import initialize_graph_management
    except ImportError:
        from bootstrap import initialize_graph_management
    initialize_graph_management()


FRONT = os.path.join(os.path.dirname(__file__), "..", "view", "graph_viewer.html")


@app.get("/")
def viewer():
    return FileResponse(os.path.abspath(FRONT))


@app.get("/health")
def health():
    return {"status": "up"}


if __name__ == "__main__":
    import sys
    # 支持 cd server && python main.py 直接运行：把项目根目录加入 sys.path
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    # reload 需要 import string；根据 CWD 选择正确的模块路径
    if os.path.basename(os.getcwd()) == "server":
        uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
    else:
        uvicorn.run("server.main:app", host="0.0.0.0", port=8001, reload=True)
