"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .api import test_type_router, device_router, test_execution_router, ws_router
from .api.config_api import router as config_router
from .api.results import router as results_router
from .api.cluster_api import router as cluster_router
from .api.ai_api import router as ai_router

app = FastAPI(title="Athena2 Product Test", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由（cluster_router 必须在 test_execution_router 之前，
# 否则 /tests/cluster 会被 /tests/{test_id} 先匹配）
app.include_router(cluster_router)
app.include_router(ai_router)
app.include_router(test_type_router)
app.include_router(device_router)
app.include_router(test_execution_router)
app.include_router(ws_router)
app.include_router(config_router)
app.include_router(results_router)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}

# 挂载前端静态文件
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 回退：所有非 API 路径返回 index.html"""
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(str(index_path))
        return {"detail": "Frontend not built"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080)
