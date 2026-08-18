import os

# app.py - Go购网页服务入口
# 运行: python src/app.py  → 浏览器打开 http://localhost:8001
import sys

from diag import diag

# pythonw 无控制台时 sys.stdout/stderr 为 None——print 会崩，重定向到文件保日志
if sys.stdout is None:
    try:
        sys.stdout = open(
            os.path.join(os.path.dirname(__file__), "..", "data", "server_stdout.log"),
            "w",
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        diag("app", "app_startup", e, "stdout 重定向失败——日志通道缺失")
if sys.stderr is None:
    try:
        sys.stderr = open(
            os.path.join(os.path.dirname(__file__), "..", "data", "server_stderr.log"),
            "w",
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        diag("app", "app_startup", e, "stderr 重定向失败——日志通道缺失")

# 2026-08-11 小布①④：pythonw 下 stdout 默认 GBK，print emoji 崩（阻塞搜索+盯价500）——全局改 UTF-8
for _s in (sys.stdout, sys.stderr):
    if _s is None:
        continue
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]  # TextIO.reconfigure 合法 API，类型检查器不认识
    except Exception as e:
        diag("app", "app_startup", e, "UTF-8 reconfigure 失败——emoji print 可能崩")

sys.path.insert(0, os.path.dirname(__file__))
import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Go购")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "templates", "static")), name="static")


@app.middleware("http")
async def no_cache(request, call_next):
    resp = await call_next(request)
    if request.url.path.endswith((".html", "/")) or not request.url.path:
        resp.headers["Cache-Control"] = "no-store"
    # 2026-08-10 TradeGuard 扫描建议：安全头（保守不加 CSP 以免破坏内联脚本/SSE）
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Server"] = "GoGou"
    return resp




# ===== 路由挂载（拆分工程 2026-08-12：路由移入 routes/ 包）=====
from routes import api as _r_api
from routes import pages as _r_pages
from routes import search as _r_search

app.include_router(_r_search.router)
app.include_router(_r_pages.router)
app.include_router(_r_api.router)

if __name__ == "__main__":
    import uvicorn

    async def _watch_loop():
        """盯价定时检查（v6 最后一环）：启动时跑一次 + 每 6 小时一次"""
        import asyncio

        while True:
            try:
                from notify import check_and_notify

                stat = await asyncio.to_thread(check_and_notify)
                print(f"[watch] 盯价检查: {stat}")
            except Exception as e:
                print(f"[watch] 检查异常: {str(e)[:80]}")
            await asyncio.sleep(6 * 3600)  # 6 小时

    import threading

    threading.Thread(target=lambda: asyncio.run(_watch_loop()), daemon=True).start()
    uvicorn.run(
        app, host="0.0.0.0", port=8001
    )  # pi-lens-ignore: bind-all-interfaces 故意 0.0.0.0：手机/家人设备局域网访问必需（防火墙已放行）
