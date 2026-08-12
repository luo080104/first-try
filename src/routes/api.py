# routes/api.py — API 路由（从 app.py 拆分，2026-08-12 路由拆分工程）
import asyncio
import os

from fastapi import APIRouter, Form

from app_state import _BACKGROUND_TASKS

router = APIRouter()

import re

from db import get_conn, init_db, stats_items


@router.get("/api/price_trend")
def api_price_trend(sku_id: str = "", platform: str = "", days: int = 30):
    """价格趋势（近 N 天，按天聚合取最后价）——price_compare_tool 借鉴"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT date(queried_at) d, price FROM price_history
        WHERE item_id=? AND platform=? AND queried_at >= datetime('now','localtime', ?)
        ORDER BY queried_at""",
        (sku_id, platform, f"-{days} days"),
    ).fetchall()
    conn.close()
    daily = {}
    for r in rows:
        daily[r["d"]] = r["price"]
    pts = [{"date": d, "price": p} for d, p in sorted(daily.items())]
    return {"ok": True, "points": pts}



@router.get("/api/search_history")
def api_search_history(user_name: str = ""):
    conn = get_conn()
    rows = conn.execute(
        """SELECT keyword, category, MAX(searched_at) searched_at
        FROM search_history WHERE user_name=? GROUP BY keyword
        ORDER BY searched_at DESC LIMIT 200""",
        (user_name,),
    ).fetchall()
    conn.close()
    return {"ok": True, "items": [dict(r) for r in rows]}



@router.post("/api/search_history_del")
def api_search_history_del(keyword: str = Form(""), user_name: str = ""):
    conn = get_conn()
    conn.execute(
        "DELETE FROM search_history WHERE keyword=? AND user_name=?",
        (keyword, user_name),
    )
    conn.commit()
    conn.close()
    return {"ok": True}



@router.post("/api/search_history_clear")
def api_search_history_clear(user_name: str = ""):
    conn = get_conn()
    conn.execute("DELETE FROM search_history WHERE user_name=?", (user_name,))
    conn.commit()
    conn.close()
    return {"ok": True}



@router.get("/history")
def history(platform: str = "tb", item_id: str = ""):
    import sqlite3

    conn = sqlite3.connect(
        os.path.join(os.path.dirname(__file__), "..", "data", "shopping.db")
    )
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT title, price, coupon_amount, queried_at FROM price_history
        WHERE platform=? AND item_id=? ORDER BY queried_at DESC LIMIT 30
    """,
        (platform, item_id),
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if result:
        prices = [r["price"] for r in result]
        result.append(
            {
                "summary": {
                    "lowest": min(prices),
                    "current": result[0]["price"],
                    "count": len(result),
                }
            }
        )
    return result



@router.post("/watch")
def watch_add(
    title: str = Form(...),
    platform: str = Form(""),
    item_id: str = Form(""),
    current_price: float = Form(...),
    target_price: float = Form(...),
):
    from db import add_watch, init_db

    init_db()
    add_watch(title[:80], platform, item_id, current_price, target_price)
    return {"ok": True}



@router.get("/api/stats")
def api_stats():
    """商品库统计接口"""
    init_db()
    return stats_items()



@router.get("/api/family")
def api_family():
    """家庭品类库（15 细品类 → 大品类 + 采集词）"""
    from db import FAMILY_CATEGORIES

    return {
        "categories": [
            {"name": sub, "big": big, "words": words}
            for sub, big, words in FAMILY_CATEGORIES
        ]
    }



@router.post("/api/family_tasks")
async def api_family_tasks(categories: str = Form("")):
    """把用户勾选的品类的采集词加入采集计划（幂等）
    categories: 逗号分隔的细品类名，如 '女士服装,护肤品'；空=全部"""
    from db import FAMILY_CATEGORIES, get_conn

    conn = get_conn()
    added = 0
    pick = (
        [c.strip() for c in categories.replace("，", ",").split(",") if c.strip()]
        if categories.strip()
        else []
    )
    for sub, big, words in FAMILY_CATEGORIES:
        if pick and sub not in pick:
            continue
        for w in words:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO crawl_tasks (keyword, category, source) VALUES (?,?, 'family')
            """,
                (w, big),
            )
            added += cur.rowcount
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "msg": f"已把 {len(pick) if pick else 15} 个品类的采集词加入计划（+{added} 个新词）",
    }



@router.post("/api/search_log")
async def api_search_log(
    user_name: str = Form(""), keyword: str = Form(""), category: str = Form("")
):
    """v6 用户记忆：记录一次搜索（教材3章）"""
    from db import log_search

    if keyword.strip():
        log_search(user_name.strip(), keyword.strip(), category)
    return {"ok": True}



@router.get("/api/profile")
def api_profile(user: str = ""):
    """v6 用户画像：最近搜索词 + 品类分布"""
    from db import user_profile

    return user_profile(user.strip())



@router.post("/api/resume_tasks")
async def api_resume_tasks():
    """经验学习：手动恢复暂停的采集任务"""
    from db import resume_crawl_tasks

    n = resume_crawl_tasks()
    return {"ok": True, "msg": f"已恢复 {n} 个暂停任务"}


# ========== v7 陪你出发（AI 购物向导）==========



@router.post("/api/chat")
async def api_chat(
    session_id: str = Form(""), user_name: str = Form(""), message: str = Form("")
):
    """陪你出发：一轮聊天"""
    import uuid

    from guide import chat

    sid = session_id.strip() or str(uuid.uuid4())
    if not message.strip():
        return {"ok": False, "msg": "说点什么吧"}
    result = await asyncio.to_thread(chat, sid, message.strip(), user_name.strip())
    return {"ok": True, "session_id": sid, **result}


# ========== v7 AI 费用统计（Agent Part 借鉴）==========



@router.get("/api/usage")
def api_usage():
    """本月 AI 费用统计"""
    from llm_usage import month_cost

    return month_cost()


# ========== v7 购物漫游（推荐闭环）==========



@router.get("/api/wander")
def api_wander(user: str = "", size: int = 12):
    """购物漫游：按画像推荐（返回卡片 + 推荐理由）"""
    from db import get_conn
    from wander import wander_recommend

    # 已不喜欢/已收藏的排除
    conn = get_conn()
    rows = conn.execute(
        "SELECT item_id FROM wander_feedback WHERE user_name=? AND action IN ('dislike','fav')",
        (user or "",),
    ).fetchall()
    conn.close()
    exclude = [r["item_id"] for r in rows if r["item_id"]]
    items = wander_recommend(user or "", min(max(size, 6), 30), exclude)
    cards = []
    for it in items:
        cards.append(
            {
                "item_id": it.get("item_id"),
                "platform": it.get("platform"),
                "title": (it.get("title") or "")[:80],
                "price": it.get("price"),
                "original_price": it.get("original_price"),
                "shop": it.get("shop_name"),
                "sales": it.get("sales"),
                "category": it.get("category"),
                "url": it.get("url"),
                "img": it.get("img"),
                "reason": _wander_reason(it, user or ""),
            }
        )
    return {"ok": True, "cards": cards}


def _wander_reason(it: dict, user: str) -> str:
    """漫游卡片推荐理由（可解释性）"""
    from guide import get_profile

    cats = get_profile(user).get("categories") or []
    cat = it.get("category") or ""
    if cat and cat in cats:
        return f"因为你最近在看{cat}"
    if it.get("sales") and it["sales"] > 10000:
        return "🔥 大家都在买"
    return "✨ 发现一个你可能没看过的"



@router.post("/api/wander_feedback")
async def api_wander_feedback(
    user: str = Form(""), item_id: str = Form(""), action: str = Form("dislike")
):
    """漫游反馈：dislike=不感兴趣 / fav=收藏"""
    from db import get_conn

    conn = get_conn()
    conn.execute(
        "DELETE FROM wander_feedback WHERE user_name=? AND item_id=? AND action=?",
        (user or "", item_id, action),
    )
    conn.execute(
        "INSERT INTO wander_feedback (user_name, item_id, action) VALUES (?,?,?)",
        (user or "", item_id, action),
    )
    conn.commit()
    conn.close()
    return {"ok": True}



@router.get("/api/wander_favs")
def api_wander_favs(user: str = ""):
    """我的收藏列表"""
    from db import get_conn

    conn = get_conn()
    rows = conn.execute(
        """SELECT f.item_id, p.title, p.price, p.platform, p.shop_name, p.url
        FROM wander_feedback f LEFT JOIN product_items p ON p.item_id = f.item_id
        WHERE f.user_name=? AND f.action='fav' ORDER BY f.id DESC""",
        (user or "",),
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


# ========== v7 评估埋点（建议采纳率闭环）==========



@router.post("/api/event")
async def api_event(
    scene: str = Form(""),
    keyword: str = Form(""),
    action: str = Form("shown"),
    user_name: str = Form(""),
    variant: str = Form("a"),
):
    """记录行为事件：shown=展示 / adopt=采纳（点击去购买/去比价），variant 供 A-B 统计"""
    from db import get_conn, init_db

    init_db()  # 确保表存在
    conn = get_conn()
    conn.execute(
        "INSERT INTO advice_events (scene, keyword, action, user_name, variant) VALUES (?,?,?,?,?)",
        (scene[:20], (keyword or "")[:60], action, user_name[:30], variant[:4]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}



@router.get("/api/advice_stats")
def api_advice_stats():
    """建议采纳率统计：adopt/shown（纯行为数据，零 LLM 成本）"""
    from db import get_conn, init_db

    init_db()  # 确保表存在
    conn = get_conn()
    shown = conn.execute(
        "SELECT COUNT(*) FROM advice_events WHERE action='shown'"
    ).fetchone()[0]
    adopt = conn.execute(
        "SELECT COUNT(*) FROM advice_events WHERE action='adopt'"
    ).fetchone()[0]
    by_scene = conn.execute("""SELECT scene, COUNT(*) n FROM advice_events WHERE action='adopt'
        GROUP BY scene ORDER BY n DESC""").fetchall()
    # v1.0 A-B：按 variant 分别统计采纳率
    by_variant = conn.execute("""SELECT variant,
        SUM(CASE WHEN action='shown' THEN 1 ELSE 0 END) shown,
        SUM(CASE WHEN action='adopt' THEN 1 ELSE 0 END) adopt
        FROM advice_events GROUP BY variant""").fetchall()
    conn.close()
    rate = round(adopt / shown * 100, 1) if shown else 0
    ab = {}
    for r in by_variant:
        s, a = r["shown"], r["adopt"]
        ab[r["variant"]] = {
            "shown": s,
            "adopt": a,
            "rate": round(a / s * 100, 1) if s else 0,
        }
    return {
        "shown": shown,
        "adopt": adopt,
        "adopt_rate": rate,
        "by_scene": [dict(r) for r in by_scene],
        "ab": ab,
    }



@router.get("/api/price_prediction")
def api_price_prediction(platform: str = "", item_id: str = ""):
    """降价预测（纯规则：斜率+低点+波动，零 LLM，小布方案）"""
    from db import get_conn
    from price_trap import predict_price

    if not item_id:
        return {"ok": False, "msg": "缺少商品 ID"}
    conn = get_conn()
    rows = conn.execute(
        """SELECT price FROM price_history
        WHERE platform=? AND item_id=? ORDER BY queried_at ASC""",
        (platform, str(item_id)),
    ).fetchall()
    conn.close()
    prices = [r["price"] for r in rows if r["price"] and r["price"] > 1]
    return {"ok": True, **predict_price(prices)}



@router.get("/api/detail")
def api_detail(platform: str = "", id: str = ""):
    """商品详情（淘宝 get-goods-details；PDD/京东暂无详情接口则返回基本信息）"""
    from db import get_conn

    if not id:
        return {"ok": False, "msg": "缺少商品 ID"}
    if platform == "tb":
        from api_client import get_goods_details

        d = get_goods_details(id)
        if d:
            return {"ok": True, **d}
    if platform == "pdd":
        from api_client import get_pdd_details

        d = get_pdd_details(id)
        if d:
            return {"ok": True, **d}
    # API 失败/不可用 → 回退商品库已有信息（保证详情总能用）
    conn = get_conn()
    row = conn.execute(
        "SELECT title, shop_name, price, sales, url, img FROM product_items WHERE item_id=? LIMIT 1",
        (id,),
    ).fetchone()
    conn.close()
    if row:
        return {
            "ok": True,
            "title": row["title"],
            "shop": row["shop_name"],
            "img": row["img"],
            "sales": row["sales"],
            "desc": "",
            "fallback": True,
        }
    return {"ok": False, "msg": "未找到商品"}



@router.post("/api/spec_compare")
async def api_spec_compare(
    keyword: str = Form(""), category: str = Form(""), group_key: str = Form("")
):
    """数码参数对比：同组商品用 DigitalMatcher 提取参数并排"""
    from compare import search_compare_slow
    from matcher import DigitalMatcher

    data = await search_compare_slow(keyword, category)
    group = next((g for g in data["groups"] if g["key"] == group_key), None)
    if not group:
        return {"ok": False, "msg": "未找到该商品组"}
    items = []
    for p, it in group["platforms"].items():
        spec = DigitalMatcher.parse(str(it.get("title") or ""))
        cfg = spec.get("config") or {}
        items.append(
            {
                "platform": p,
                "price": it.get("actualPrice"),
                "title": (it.get("title") or "")[:40],
                "spec": {
                    "型号": spec.get("series") or "-",
                    "GPU": cfg.get("gpu") or "-",
                    "CPU": cfg.get("cpu") or "-",
                    "内存": cfg.get("ram") or "-",
                    "存储": cfg.get("storage") or "-",
                },
            }
        )
    return {"ok": True, "keyword": keyword, "items": items[:4]}



@router.post("/api/debate")
async def api_debate(
    keyword: str = Form(""), category: str = Form(""), group_key: str = Form("")
):
    """多视角辩论：三派各自点评（分角色 prompt）"""
    from compare import gen_debate, search_compare_slow

    data = await search_compare_slow(keyword, category)
    group = next((g for g in data["groups"] if g["key"] == group_key), None)
    if not group:
        return {"ok": False, "msg": "未找到该商品组"}
    views = await asyncio.to_thread(gen_debate, keyword, group)
    return {"ok": True, "views": views}


# ========== v8.5 热搜联想 + 相似推荐（大淘客现成接口）==========



@router.get("/api/hotwords")
def api_hotwords():
    """热搜榜（首页'大家正在搜'）"""
    from api_client import get_hot_words

    return {"words": get_hot_words()}



@router.get("/api/similar")
def api_similar(id: str = ""):
    """相似商品（猜你喜欢）"""
    from api_client import get_similar_goods

    items = get_similar_goods(id, 8) if id else []
    return {"items": items}


# ========== v8 邀请码（WorkBuddy 极简设计：一张表+两个页面）==========



@router.post("/api/invite_gen")
async def api_invite_gen(user_name: str = Form(""), categories: str = Form("")):
    """生成邀请码（管理员）：Go-xxxx 6 位，绑定角色名+品类"""
    import secrets

    from db import get_conn, init_db

    init_db()
    if not user_name.strip():
        return {"ok": False, "msg": "请填角色名（如：妈妈）"}
    code = "Go-" + secrets.token_hex(2).lower()
    conn = get_conn()
    conn.execute(
        "INSERT INTO invite_codes (code, user_name, categories) VALUES (?,?,?)",
        (code, user_name.strip()[:30], categories or "[]"),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "code": code, "user_name": user_name.strip()}



@router.post("/api/invite_use")
async def api_invite_use(code: str = Form(""), device_id: str = Form("")):
    """亲戚端：输入邀请码 → 校验未用 → 返回角色信息 + 标记已用"""
    from db import get_conn, init_db

    init_db()
    code = code.strip()
    conn = get_conn()
    row = conn.execute("SELECT * FROM invite_codes WHERE code=?", (code,)).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "msg": "邀请码不存在，检查一下？"}
    if row["used_at"]:
        conn.close()
        return {"ok": False, "msg": "这个邀请码已被使用过了"}
    conn.execute(
        "UPDATE invite_codes SET used_at=datetime('now','localtime'), used_by=? WHERE id=?",
        (device_id[:50], row["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "user_name": row["user_name"], "categories": row["categories"]}



@router.get("/api/invite_list")
def api_invite_list():
    """邀请码列表（管理页）"""
    from db import get_conn, init_db

    init_db()
    conn = get_conn()
    rows = conn.execute(
        "SELECT code, user_name, categories, used_at, created_at FROM invite_codes ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


# ========== v5 采集引擎接口 ==========



@router.post("/api/crawl")
async def api_crawl(pages: int = Form(2), max_minutes: int = Form(480)):
    """启动一轮采集（后台任务，进度查 /api/crawl_status）。
    max_minutes: 硬性时长上限（默认 480 分钟 = 8 小时），到点自动停"""
    from crawl import get_progress, run_crawl_round

    if get_progress().get("running"):
        return {"ok": False, "msg": "采集已在运行中，请稍候"}
    pages = min(max(pages, 1), 5)
    max_minutes = min(
        max(max_minutes, 10), 1200
    )  # 10 分钟 ~ 20 小时（P1-1：对齐 crawl 20h 上限）
    _BACKGROUND_TASKS.add(
        asyncio.create_task(run_crawl_round(pages, max_seconds=max_minutes * 60))
    )
    return {
        "ok": True,
        "msg": f"采集已启动（每词翻 {pages} 页，最长跑 {max_minutes} 分钟，到点自动停）",
    }



@router.get("/api/crawl_status")
def api_crawl_status():
    """采集进度（前端轮询）"""
    from crawl import get_progress

    return get_progress()



@router.get("/api/crawl_tasks")
def api_crawl_tasks():
    """任务表（采集中心页）"""
    from db import crawl_stats, list_crawl_tasks

    init_db()
    return {"tasks": list_crawl_tasks(), "stats": crawl_stats()}



@router.post("/api/crawl_add")
async def api_crawl_add(keyword: str = Form(""), category: str = Form("")):
    """手动加采集词（小白友好：只填词）"""
    from db import get_conn

    kw = keyword.strip()
    if not kw:
        return {"ok": False, "msg": "请输入关键词"}
    conn = get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO crawl_tasks (keyword, category, source) VALUES (?,?,?)",
        (kw[:30], category or "", "manual"),
    )
    conn.commit()
    conn.close()
    return {
        "ok": True,
        "msg": "已加入采集计划" if cur.rowcount else "这个词已在计划里了",
    }



@router.post("/api/prefs")
async def api_prefs(prefs: str = Form("")):
    """偏好设置（v5.2）：逗号分隔排除平台，空=清除"""
    from db import PREF_EXCLUDE_PLATFORMS, set_user_pref

    PLAT_MAP = {
        "拼多多": "pdd",
        "京东": "jd",
        "淘宝": "tb",
        "唯品会": "vip",
        "pdd": "pdd",
        "jd": "jd",
        "tb": "tb",
        "vip": "vip",
    }
    if not prefs.strip():
        set_user_pref(PREF_EXCLUDE_PLATFORMS, [])
        return {"ok": True, "msg": "已清除排除平台"}
    plats = []
    for w in prefs.replace("，", ",").split(","):
        w = w.strip()
        if w in PLAT_MAP and PLAT_MAP[w] not in plats:
            plats.append(PLAT_MAP[w])
    if not plats:
        return {"ok": False, "msg": "没认出来平台名，试试：拼多多/京东/淘宝/唯品会"}
    set_user_pref(PREF_EXCLUDE_PLATFORMS, plats)
    return {
        "ok": True,
        "msg": "已记住：排除 "
        + "、".join(plats)
        + '（对话里说"不要拼多多"也能自动记住）',
    }



@router.post("/api/compare")
async def api_compare(keyword: str = Form(""), category: str = Form("")):
    """四平台搜索（快通道 + 京东/唯品会慢通道）+ SKU 合并 + 内容摘要"""
    from compare import content_summary, parse_link, search_compare_slow

    kw = keyword.strip()
    link_info = parse_link(kw)
    # 链接输入：提取平台+ID，用 ID 查不到详情就回退为关键词搜索
    if link_info:
        kw = re.sub(r"https?://\S+", "", kw).strip() or kw
    if not kw:
        return {"ok": False, "msg": "请输入商品关键词或链接"}
    data = await search_compare_slow(kw, category)
    content = await asyncio.to_thread(content_summary, kw)
    return {
        "ok": True,
        "keyword": kw,
        "groups": [
            {
                "key": g["key"],
                "platforms": [
                    {
                        "platform": p,
                        "title": it.get("title", ""),
                        "price": it.get("actualPrice"),
                        "original": it.get("originalPrice"),
                        "coupon": it.get("couponPrice") or it.get("coupon_amount") or 0,
                        "shop": it.get("shopName") or "",
                        "url": it.get("url") or "",
                        "goodsId": it.get("goodsId") or "",
                        "sales": it.get("monthSales") or 0,
                        "shop_type": it.get("shop_type") or "",
                        "unit_price": it.get("unit_price"),
                        "shop_rating": it.get("shop_rating"),
                        "shop_signals": it.get("shop_signals"),
                    }
                    for p, it in g["platforms"].items()
                ],
                "best_price": g["best"]["actualPrice"],
                "low_price_warning": g.get("low_price_warning", False),
                "genuine": g.get("genuine"),
            }
            for g in data["groups"][:6]
        ],
        "subsidies": data["subsidies"],
        "content": content,
        "tb_count": data["tb_count"],
        "pdd_count": data["pdd_count"],
        "jd_count": data.get("jd_count", 0),
        "vip_count": data.get("vip_count", 0),
    }



@router.post("/api/advice")
async def api_advice(
    keyword: str = Form(""), category: str = Form(""), group_key: str = Form("")
):
    """AI 建议面板（V4-Pro，异步加载 + 6h 缓存，WorkBuddy P1-3）"""
    from compare import gen_advice, search_compare_slow
    from db import get_advice_cache, get_conn, save_advice_cache

    cache_key = f"{keyword.strip()}|{group_key.strip()}"
    cached = get_advice_cache(cache_key)
    if cached:
        return {"ok": True, "advice": cached, "cached": True}
    data = await search_compare_slow(keyword, category)
    group = next((g for g in data["groups"] if g["key"] == group_key), None)
    if not group:
        return {"ok": False, "msg": "未找到该商品组"}
    # 查历史（取组内第一个有 goodsId 的商品）
    history = []
    conn = get_conn()
    for p, it in group["platforms"].items():
        gid = it.get("goodsId") or ""
        if gid:
            rows = conn.execute(
                """
                SELECT price, queried_at FROM price_history
                WHERE platform=? AND item_id=? ORDER BY queried_at DESC LIMIT 30
            """,
                (p, str(gid)),
            ).fetchall()
            history += [dict(r) for r in rows]
            break
    conn.close()
    # v1.0 A-B 实验分流：按 user_name 稳定 hash → variant（a=新版prompt / b=旧版）
    variant = "a" if (sum(ord(c) for c in keyword) % 2 == 0) else "b"
    advice = await asyncio.to_thread(
        gen_advice, keyword, group, data["subsidies"], history, variant
    )
    if not advice.startswith("【当前位】AI 建议暂时不可用"):
        save_advice_cache(cache_key, advice)
    # v7 评估埋点：建议展示记录（shown，带 variant 供 A-B 统计）
    try:
        from db import get_conn

        conn = get_conn()
        conn.execute(
            "INSERT INTO advice_events (scene, keyword, action, variant) VALUES (?,?,?,?)",
            ("compare", keyword[:60], "shown", variant),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return {"ok": True, "advice": advice, "cached": False, "variant": variant}


# ========== v7 商品库分析（Taobao_Spider 可视化看板借鉴，ECharts 版）==========



@router.get("/api/analysis")
def api_analysis():
    """商品库分析：价格分布 + 品牌占比 + 价格销量散点 + 平台分布 + 入库趋势（供看板图表）"""
    from db import get_conn

    conn = get_conn()
    # 2026-08-11 仪表盘增强：平台分布 + 近 7 天入库趋势
    plat_dist = [
        dict(r)
        for r in conn.execute(
            """SELECT platform, COUNT(*) n FROM product_items GROUP BY platform ORDER BY n DESC"""
        ).fetchall()
    ]
    in_trend = [
        dict(r)
        for r in conn.execute("""SELECT date(first_seen) d, COUNT(*) n FROM product_items
        WHERE first_seen >= date('now','localtime','-6 day') GROUP BY d ORDER BY d""").fetchall()
    ]
    # 价格区间分布
    bins = [(0, 100), (100, 300), (300, 1000), (1000, 3000), (3000, 999999)]
    labels = ["0-100", "100-300", "300-1000", "1000-3000", "3000+"]
    price_hist = []
    for (lo, hi), lb in zip(bins, labels):
        n = conn.execute(
            "SELECT COUNT(*) FROM product_items WHERE price >= ? AND price < ?",
            (lo, hi),
        ).fetchone()[0]
        price_hist.append({"range": lb, "n": n})
    # 品牌 TOP8 占比
    brands = conn.execute("""SELECT brand, COUNT(*) n FROM product_items
        WHERE brand != '' GROUP BY brand ORDER BY n DESC LIMIT 8""").fetchall()
    total = (
        conn.execute("SELECT COUNT(*) FROM product_items WHERE brand != ''").fetchone()[
            0
        ]
        or 1
    )
    brand_share = [{"name": r["brand"], "value": r["n"]} for r in brands]
    # 价格 vs 销量散点（样本 300 条）
    scatter = [
        {"price": r["price"], "sales": r["sales"]}
        for r in conn.execute(
            "SELECT price, sales FROM product_items WHERE price > 0 AND sales > 0 ORDER BY id DESC LIMIT 300"
        )
    ]
    conn.close()
    return {
        "price_hist": price_hist,
        "brand_share": brand_share,
        "brand_total": total,
        "scatter": scatter,
        "total": total,
        "plat_dist": plat_dist,
        "in_trend": in_trend,
    }



