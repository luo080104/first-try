# app_state.py — 应用共享状态（2026-08-12 路由拆分工程：打破 app↔routes 循环 import）
# app.py / routes/* 都从这里取共享符号
import os

from fastapi.templating import Jinja2Templates

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

CATEGORIES = ["", "服饰", "食品", "日用百货", "数码家电"]

_BACKGROUND_TASKS: set = set()  # 采集任务强引用容器（防 GC 回收未完成任务）

# Langfuse LLM 追踪（2026-08-12 小布③）：有 key 才启用，无 key 静默降级
_langfuse = None
try:
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        from langfuse import Langfuse

        _langfuse = Langfuse()  # key 从环境变量读（best practices：env 加载后再 import）
except Exception:
    _langfuse = None


def _trace_llm(scene: str, **fields):
    """追踪辅助：有 Langfuse 用 observe 风格记录，无则跳过（不抛错）"""
    if _langfuse is None:
        return None
    try:
        from langfuse import observe

        @observe(name=f"go_gou/{scene}", capture_input=True)
        def _wrapped():
            return fields

        return _wrapped()
    except Exception:
        return None
