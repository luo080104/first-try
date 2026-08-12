# routes/pages.py — 页面路由（从 app.py 拆分，2026-08-12 路由拆分工程）
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app_state import CATEGORIES, templates
from db import check_watches, init_db, list_watches, save_manual_price, stats_items

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"categories": CATEGORIES})



@router.get("/hist")
def hist_page(request: Request):
    """搜索历史页（浏览器风格：按天分组/点击即搜/单删/清空）"""
    return templates.TemplateResponse(request, "hist.html", {})



@router.get("/submit", response_class=HTMLResponse)
def submit_page(request: Request):
    return templates.TemplateResponse(request, "submit.html", {})



@router.post("/submit", response_class=HTMLResponse)
def submit_post(
    request: Request,
    keyword: str = Form(...),
    title: str = Form(...),
    platform: str = Form("other"),
    shop_name: str = Form(""),
    price: float = Form(...),
    url: str = Form(""),
    note: str = Form(""),
):
    if price <= 0 or price > 9999999:  # AI审查建议：输入验证
        return templates.TemplateResponse(
            request,
            "submit.html",
            {"success": False, "keyword": keyword, "msg": "价格需为正数"},
        )
    init_db()
    save_manual_price(
        keyword.strip(),
        title.strip(),
        platform,
        shop_name.strip(),
        price,
        url.strip(),
        note.strip(),
    )
    return templates.TemplateResponse(
        request, "submit.html", {"success": True, "keyword": keyword}
    )



@router.get("/watches", response_class=HTMLResponse)
def watches_page(request: Request):
    init_db()
    rows = list_watches()
    hits = check_watches()
    return templates.TemplateResponse(
        request, "watches.html", {"watches": rows, "hits": hits}
    )


# ========== v4 商品库 ==========



@router.get("/items", response_class=HTMLResponse)
def items_page(request: Request):
    """商品库浏览页"""
    init_db()
    stats = stats_items()
    return templates.TemplateResponse(
        request, "items.html", {"stats": stats, "categories": CATEGORIES}
    )



@router.get("/guide", response_class=HTMLResponse)
def guide_page(request: Request):
    """陪你出发：聊天式购物向导"""
    return templates.TemplateResponse(request, "guide.html", {"categories": CATEGORIES})



@router.get("/wander", response_class=HTMLResponse)
def wander_page(request: Request):
    """购物漫游：无目标浏览（多路召回推荐流）"""
    return templates.TemplateResponse(request, "wander.html", {})



@router.get("/crawl", response_class=HTMLResponse)
def crawl_page(request: Request):
    """采集中心页"""
    return templates.TemplateResponse(request, "crawl.html", {})


# ========== v3.5 对比页（Mode 2「帮我比」）==========



@router.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request):
    """对比页入口"""
    return templates.TemplateResponse(
        request, "compare.html", {"categories": CATEGORIES}
    )



