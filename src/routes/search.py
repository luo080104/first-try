# routes/search.py — 搜索路由（从 app.py 拆分，2026-08-12 路由拆分工程）
from contextlib import closing

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app_state import CATEGORIES, templates

router = APIRouter()

import asyncio
import json as _json
import re

from api_client import search_goods, search_pdd, value_score
from content_reader import read_content_items
from llm_parse import generate_options, parse_intent


def search_taobao_full(
    keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False
) -> list:
    """淘宝全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import tb_search

        items = tb_search.search_taobao(keyword, max_items=max_items, page=page)
        for it in items:
            if "actualPrice" not in it and it.get("price") is not None:
                it["actualPrice"] = it["price"]
            it["monthSales"] = it.get("sales") or it.get("real_sales") or 0
            it["shopName"] = it.get("shop_name") or it.get("shop") or ""
            it["title"] = it.get("title", "")
            # platform 已由 tb_search 统一返回 'tb'（WorkBuddy P2-1：删除死代码覆写）
            it["_source"] = "browser"
        return items
    except Exception as e:
        from errors import CaptchaError

        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f"[tb_full] 验证码，跳过（{str(e)[:40]}）")
            return []
        print(f"[tb_full] 失败: {str(e)[:80]}")
        return []


def search_jd_full(
    keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False
) -> list:
    """京东全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import jd_search

        items = jd_search.search_jd(keyword, max_items=max_items, page=page)
        for it in items:
            if "actualPrice" not in it and it.get("price") is not None:
                it["actualPrice"] = it["price"]
            it["monthSales"] = it.get("sales") or 0
            it["shopName"] = it.get("shop") or ""
            it["title"] = it.get("title", "")
            it["platform"] = "jd"
            it["_source"] = "browser"
        return items
    except Exception as e:
        from errors import CaptchaError

        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f"[jd_full] 验证码，跳过（{str(e)[:40]}）")
            return []
        print(f"[jd_full] 失败: {str(e)[:80]}")
        return []


def search_vip_full(keyword: str, page: int = 1, max_items: int = 8) -> list:
    """唯品会全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice"""
    try:
        import vip_search

        items = vip_search.search_vip(keyword, max_items=max_items, page=page)
        for it in items:
            if "actualPrice" not in it and it.get("price") is not None:
                it["actualPrice"] = it["price"]
            it["monthSales"] = it.get("sales") or 0
            it["shopName"] = it.get("shop") or ""
            it["title"] = it.get("title", "")
            it["platform"] = "vip"
            it["_source"] = "browser"
        return items
    except Exception as e:
        print(f"[vip_full] 失败: {str(e)[:80]}")
        return []


def search_pdd_full(
    keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False
) -> list:
    """拼多多全量搜索（慢通道，浏览器 H5），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import pdd_search

        items = pdd_search.search_pdd(keyword, max_items=max_items, page=page)
        for it in items:
            if "actualPrice" not in it and it.get("price") is not None:
                it["actualPrice"] = it["price"]
            it["monthSales"] = it.get("sales") or 0
            it["shopName"] = it.get("shop") or ""
            it["title"] = it.get("title", "")
            it["platform"] = "pdd"
            it["_source"] = "browser"
        return items
    except Exception as e:
        from errors import CaptchaError

        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f"[pdd_full] 验证码，跳过（{str(e)[:40]}）")
            return []
        print(f"[pdd_full] 失败: {str(e)[:80]}")
        return []


from db import (
    find_manual_prices,
    find_subsidies,
    get_conn,
    init_db,
    list_recommendations,
    query_items,
    save_search_result,
    upsert_product_item,
)
from matcher import ADAPTERS, group_by_sku, parse_items


@router.get("/search_bili")
def search_bili_api(keyword: str = ""):
    import os
    import subprocess
    import time

    # 1. 确保 Edge CDP 在跑（9222）
    import urllib.request

    cdp_ok = False
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3)
        cdp_ok = True
    except Exception:
        pass
    if not cdp_ok:
        edge = next(
            (
                p
                for p in [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                ]
                if os.path.exists(p)
            ),
            None,
        )
        if not edge:
            edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        subprocess.Popen(
            [
                edge,
                "--remote-debugging-port=9222",
                "--user-data-dir=" + os.path.expanduser("~/mc_edge_profile"),
                "about:blank",
            ],
            creationflags=0x08000000,
        )
        time.sleep(5)

    # 2. 先读已有 jsonl（复用 read_content_items：过滤+均衡+可信度打分+套路检测）
    mc_dir = os.path.expanduser("~/mc_ref")
    cached = read_content_items(keyword)
    if len(cached.get("items", [])) >= 5:
        return cached

    # 3. 缓存不足才调 MediaCrawler（uv 路径）
    uv = os.path.expanduser(r"~/AppData/Local/Programs/Python/Python314/Scripts/uv.exe")
    env = dict(os.environ, PATH=os.path.dirname(uv) + ";" + os.environ.get("PATH", ""))
    try:
        subprocess.run(
            [
                uv,
                "run",
                "main.py",
                "--platform",
                "bili",
                "--type",
                "search",
                "--keywords",
                keyword,
            ],
            cwd=mc_dir,
            env=env,
            timeout=150,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        print(f"[content] 抓取超时（150s）: {keyword[:40]}")

    # 4. 抓取后重读（含三平台 + 打分）
    return read_content_items(keyword)


@router.get("/search_tb")
def search_tb_api(keyword: str = ""):
    import tb_search

    items = tb_search.search_taobao(keyword, max_items=10)
    return {"items": items}


@router.get("/search_jd")
def search_jd_api(keyword: str = ""):
    import jd_search

    items = jd_search.search_jd(keyword, max_items=8)
    return {"items": items}


@router.get("/search_pdd")
def search_pdd_api(keyword: str = ""):
    """拼多多浏览器补搜（v6.1 打通）"""
    import pdd_search

    items = pdd_search.search_pdd(keyword, max_items=10)
    return {"items": items}


def _f(v: str) -> float:
    """空串/非法输入 -> 0（前端 URLSearchParams 会传空串）"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


@router.get("/api/items")
def api_items(
    keyword: str = "",
    category: str = "",
    platform: str = "",
    min_price: str = "",
    max_price: str = "",
    sort: str = "price_asc",
    page: int = 1,
    size: int = 30,
):
    """商品库查询接口"""
    init_db()
    return query_items(
        keyword.strip(),
        category,
        platform,
        _f(min_price),
        _f(max_price),
        sort,
        max(1, page),
        min(max(1, size), 100),
    )


@router.post("/api/extract")
async def api_extract(keyword: str = Form("")):
    """内容→商品抽取（DeepSeek）→ recommendations 入库"""
    from extract_products import run_extract

    result = await asyncio.to_thread(run_extract, keyword.strip())
    return result


@router.get("/api/recommendations")
def api_recommendations(limit: int = 50):
    """博主推荐列表（按商品聚合）"""
    init_db()
    return {"items": list_recommendations(limit)}


@router.post("/api/deep_crawl")
async def api_deep_crawl(
    keyword: str = Form(...), category: str = Form(""), pages: int = Form(3)
):
    """深度采集：淘宝+京东浏览器翻页采集（用户主动触发，低频约束）→ 沉淀入库"""
    keyword = keyword.strip()
    if not keyword:
        return {"ok": False, "msg": "请输入关键词"}
    pages = min(max(pages, 1), 5)
    results: dict = {"tb": [], "jd": [], "vip": []}
    # 淘宝翻页（tb_search 已支持 page）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_taobao_full, keyword, p)
            results["tb"] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f"[deep_crawl tb] {str(e)[:80]}")
    # 京东翻页（含 30s 低频约束，3 页约 1.5 分钟）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_jd_full, keyword, p)
            results["jd"] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f"[deep_crawl jd] {str(e)[:80]}")
    # 唯品会翻页（12-20s 随机抖动）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_vip_full, keyword, p)
            results["vip"] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f"[deep_crawl vip] {str(e)[:80]}")
    # 入库
    with closing(get_conn()) as conn:
        added = 0
        for plat, items in results.items():
            for it in items:
                it["_source"] = "browser"
                if upsert_product_item(conn, it, category or ""):
                    added += 1
        conn.commit()
    total = sum(len(v) for v in results.values())
    return {
        "ok": True,
        "msg": f"采集完成：淘宝 {len(results['tb'])} + 京东 {len(results['jd'])} + 唯品会 {len(results['vip'])} = {total} 条，入库 {added} 条",
    }


@router.get("/search_sse")
async def search_sse(  # type: ignore[misc]  # generator 内 return 值合法（Python 3.3+），pyright 严格模式误报
    request: Request,
    keyword: str = "",
    category: str = "",
    guide_round: int = 0,
    mode: str = "live",
    user_name: str = "",
    session_id: str = "",
    pin: str = "",
):
    """搜索 SSE。mode=history 看以往数据（读库秒出）；mode=live 实时报告（绕过缓存现场抓）
    2026-08-13 小布🟡3：客户端断开检测——不挂死生成器
    2026-08-13 小布🔴2：设置 PIN 后历史模式需校验（live 模式不校验——防日常搜索卡壳）"""
    from db import verify_pin

    if mode == "history" and not verify_pin(pin or ""):
        _err = _json.dumps(
            {"type": "error", "msg": "访问密码不对（或未设置密码）"}, ensure_ascii=False
        )
        return StreamingResponse(
            iter([b"data: " + _err.encode("utf-8") + b"\n\n"]),
            media_type="text/event-stream",
        )

    async def gen():
        nonlocal keyword, category

        async def _aborted() -> bool:
            # 客户端断开 → 提前退出（不挂死慢通道）
            try:
                return await request.is_disconnected()
            except Exception:
                return False

        def sse(data):
            return "data: " + _json.dumps(data, ensure_ascii=False) + chr(10) + chr(10)

        def step(name, status):
            # 步骤可视化（Agent Part 借鉴：pending/running/completed）
            return sse({"type": "step", "step": name, "status": status})

        try:
            # v6 用户记忆：记录本次搜索（教材3章）
            try:
                from db import log_search

                log_search(user_name.strip(), keyword.strip(), category)
            except Exception:
                pass
            # ===== 📚 历史模式：只读商品库，零 API 零爬虫 =====
            if mode == "history":
                yield step("查询商品库", "running")
                yield sse({"type": "progress", "msg": "📚 历史模式：正在查询商品库..."})
                from db import query_items

                init_db()
                data = await asyncio.to_thread(
                    query_items, keyword.strip(), category, "", 0, 0, "price_asc", 1, 30
                )
                items = data.get("items", [])
                # 2026-08-11 类型归类排序：笔记本>整机>显卡>配件>其他（用户搜「5090电脑」不想先看显卡）
                from matcher import classify_digital

                # 2026-08-11 仅数码场景启用类型排序（防 T恤等非数码商品被误排）
                kw_l = (keyword or "").lower()
                is_digital = ("数码家电" in (category or "")) or any(
                    k in kw_l
                    for k in (
                        "5090",
                        "5070",
                        "5060",
                        "rtx",
                        "gtx",
                        "显卡",
                        "电脑",
                        "笔记本",
                        "主机",
                        "手机",
                        "游戏本",
                        "台式",
                        "cpu",
                        "内存",
                        "固态",
                        "显示器",
                    )
                )
                _TORDER = {"笔记本": 0, "整机": 1, "显卡": 2, "配件": 3, "其他": 4}
                groups = []
                for it in items:
                    gtype = (
                        classify_digital(it.get("title") or "") if is_digital else ""
                    )
                    groups.append(
                        {
                            "key": (it.get("title") or "")[:30],
                            "count": 1,
                            "type": gtype,
                            "platforms": [
                                {
                                    "platform": it.get("platform"),
                                    "title": it.get("title"),
                                    "actualPrice": it.get("price"),
                                    "shopName": it.get("shop_name"),
                                    "url": it.get("url"),
                                    "goodsId": it.get("item_id"),
                                    "monthSales": it.get("sales"),
                                }
                            ],
                            "best": {
                                "actualPrice": it.get("price"),
                                "title": it.get("title"),
                            },
                        }
                    )
                if is_digital:
                    groups.sort(
                        key=lambda g: (
                            _TORDER.get(g.get("type"), 9),
                            g["best"]["actualPrice"] or 999999,
                        )
                    )
                content = await asyncio.to_thread(read_content_items, keyword)
                subsidies = await asyncio.to_thread(find_subsidies, keyword, category)
                yield step("查询商品库", "done")
                yield sse(
                    {
                        "type": "done",
                        "keyword": keyword,
                        "category": category,
                        "groups": groups,
                        "total": len(items),
                        "tb_count": 0,
                        "pdd_count": 0,
                        "manual_count": 0,
                        "content": content,
                        "slow_count": 0,
                        "options": [],
                        "degraded": data.get("degraded"),
                        "degraded_kw": data.get("degraded_kw"),
                        "subsidies": subsidies,
                        "mode": "history",
                    }
                )
                return

            # ===== ⚡ 实时模式：现场抓取 =====
            yield sse({"type": "progress", "msg": "⚡ 实时模式：绕过缓存现场抓取..."})
            # 意图解析（对话式输入支持）
            yield step("理解需求", "running")
            intent = await asyncio.to_thread(parse_intent, keyword)
            yield step("理解需求", "done")
            search_kw = intent.get("keyword") or keyword
            search_cat = intent.get("category") or category
            if search_kw != keyword or search_cat != category:
                yield sse(
                    {
                        "type": "progress",
                        "msg": f"🤖 明白了：搜索「{search_kw}」"
                        + (f"（{search_cat}）" if search_cat else ""),
                    }
                )
            keyword, category = search_kw, search_cat
            # 快通道：API 并行（v5.2 加唯品会）
            yield step("搜索淘宝/拼多多/唯品会", "running")
            yield sse({"type": "progress", "msg": "🔍 帮你搜下淘宝、拼多多、唯品会～"})
            from api_client import search_vip

            tb_items, pdd_items, vip_items = await asyncio.gather(
                asyncio.to_thread(
                    search_goods, keyword, category or None, 1, 20, False
                ),
                asyncio.to_thread(search_pdd, keyword, 1, 20, False),
                asyncio.to_thread(search_vip, keyword, 1, 20, False),
            )
            # v5.2 偏好：排除平台过滤（"不要拼多多"自动记住）
            from db import get_excluded_platforms

            excluded = get_excluded_platforms()
            if excluded:
                before = len(tb_items) + len(pdd_items) + len(vip_items)
                tb_items = [i for i in tb_items if i.get("platform") not in excluded]
                pdd_items = [i for i in pdd_items if i.get("platform") not in excluded]
                vip_items = [i for i in vip_items if i.get("platform") not in excluded]
                after = len(tb_items) + len(pdd_items) + len(vip_items)
                if after != before:
                    yield sse(
                        {
                            "type": "progress",
                            "msg": f"🔕 已按你的偏好排除：{'、'.join(excluded)}",
                        }
                    )
            all_items = tb_items + pdd_items + vip_items

            # 慢通道自动补搜：快通道结果少（<5 条）→ 全网补搜；或拼多多 API 被限（返回空）→ 拼多多浏览器兜底
            slow_items = []
            if len(all_items) < 5:
                if await _aborted():
                    return
                yield sse(
                    {
                        "type": "progress",
                        "msg": "这波没搜到啥合适的，我再帮你把淘宝、京东、唯品会、拼多多都翻一遍…",
                    }
                )
                tb_full, jd_full, vip_full, pdd_full = await asyncio.gather(
                    asyncio.to_thread(search_taobao_full, keyword, 15),
                    asyncio.to_thread(search_jd_full, keyword, 15),
                    asyncio.to_thread(search_vip_full, keyword, 15),
                    asyncio.to_thread(search_pdd_full, keyword, 15),
                )
                slow_items = tb_full + jd_full + vip_full + pdd_full
                all_items = all_items + slow_items
                # 2026-08-10 过滤服务类/租赁类商品（云渲染/远程渲染/出租/小时计费等非实物）
                service_kw = (
                    "远程渲染",
                    "云渲染",
                    "渲染农场",
                    "云电脑",
                    "出租",
                    "租用",
                    "小时计费",
                    "显卡租赁",
                    "gpu租赁",
                    "云服务",
                    "按小时",
                    "代练",
                    "充值",
                    "会员",
                )
                before = len(all_items)
                all_items = [
                    it
                    for it in all_items
                    if not any(k in (it.get("title") or "") for k in service_kw)
                ]
                if len(all_items) != before:
                    yield sse(
                        {
                            "type": "progress",
                            "msg": f"🧹 已过滤 {before - len(all_items)} 条服务/租赁类商品",
                        }
                    )
                # 2026-08-11 平台透明（省柴柴借鉴）：哪家找到多少明说
                _plat_n = [
                    f"{p} {n} 条"
                    for p, n in (
                        ("淘宝", len(tb_full)),
                        ("京东", len(jd_full)),
                        ("唯品会", len(vip_full)),
                        ("拼多多", len(pdd_full)),
                    )
                    if n
                ]
                yield sse(
                    {
                        "type": "progress",
                        "msg": f"✅ 翻完了！找到 {len(slow_items)} 条（"
                        + "、".join(_plat_n)
                        + "），正在给你挑…",
                    }
                )
            elif not pdd_items:
                # 拼多多 API 被限流/失败 → 浏览器通道兜底（2026-08-10 实测 duoId 被限）
                yield sse(
                    {
                        "type": "progress",
                        "msg": "拼多多 API 暂时受限，改用浏览器补拼多多...",
                    }
                )
                slow_items = await asyncio.to_thread(search_pdd_full, keyword)
                all_items = tb_items + pdd_items + vip_items + slow_items
                yield sse(
                    {
                        "type": "progress",
                        "msg": f"✅ 翻完了！找到 {len(slow_items)} 条，正在给你挑…",
                    }
                )
            else:
                yield sse(
                    {
                        "type": "progress",
                        "msg": f"✅ 淘宝 {len(tb_items)} 条 + 拼多多 {len(pdd_items)} 条 + 唯品会 {len(vip_items)} 条，正在 SKU 分组...",
                    }
                )

            yield step("搜索平台", "done")
            yield step("比价合并", "running")
            init_db()
            groups = []
            if category and category in ADAPTERS:
                parsed = parse_items(all_items, category)
                grouped = group_by_sku(parsed, category)
                for key, items in grouped.items():
                    if not key or key == "未解析":
                        continue
                    by_platform: dict = {}
                    for it in items:
                        it["value_score"] = value_score(it)
                        p = it.get("platform", "?")
                        if (
                            p not in by_platform
                            or it["actualPrice"] < by_platform[p]["actualPrice"]
                        ):
                            by_platform[p] = it
                    best = min(by_platform.values(), key=lambda x: x["actualPrice"])
                    groups.append(
                        {
                            "key": key,
                            "count": len(items),
                            "platforms": sorted(
                                by_platform.values(), key=lambda x: x["actualPrice"]
                            ),
                            "best": best,
                        }
                    )
                groups.sort(key=lambda g: g["best"]["actualPrice"])
            else:
                for it in all_items[:20]:
                    groups.append(
                        {
                            "key": it["title"][:30],
                            "count": 1,
                            "platforms": [it],
                            "best": it,
                        }
                    )

            # v5.2 低价警示（WorkBuddy 提级 P0）：组内最低价 < 均价 70% → 防二手/仿品/单只
            from matcher import annotate_group

            for g in groups:
                annotate_group(g, category or "")
                plats = g.get("platforms") or []
                if isinstance(plats, list) and len(plats) >= 2:
                    ps = [p["actualPrice"] for p in plats if p.get("actualPrice")]
                    if len(ps) >= 2 and min(ps) < (sum(ps) / len(ps)) * 0.7:
                        g["low_price_warning"] = True

            manual_items = find_manual_prices(keyword)
            for m in manual_items:
                groups.append(
                    {
                        "key": f"人工录入: {m['title'][:20]}",
                        "count": 1,
                        "platforms": [
                            {
                                "platform": m["platform"],
                                "title": m["title"],
                                "actualPrice": m["price"],
                                "originalPrice": None,
                                "shopName": m["shop_name"] + "（人工录入）",
                                "url": m["url"],
                            }
                        ],
                        "best": None,
                    }
                )

            with closing(get_conn()) as conn:
                for it in all_items:
                    save_search_result(conn, it, category or "未分类")
                    upsert_product_item(conn, it, category or "")
                conn.commit()

            # 对话式导购：触发条件（WorkBuddy 审核）——先导购后补搜
            options = []
            prices = [
                g["best"]["actualPrice"]
                for g in groups
                if g.get("best") and g["best"].get("actualPrice")
            ]
            has_model_num = bool(re.search(r"\d{2,}", keyword))
            # v5.2 需求三要素追问（WorkBuddy P1）：宽泛品类词才问，带"直接搜→"跳过
            if (
                guide_round == 0
                and search_cat
                and not has_model_num
                and len(groups) >= 3
            ):
                yield sse(
                    {
                        "type": "need",
                        "q": "💸 大概什么预算？（可跳过）",
                        "options": [
                            {"label": "💸 ≤3000", "value": "3000"},
                            {"label": "💸 3000-8000", "value": "8000"},
                            {"label": "💸 8000+", "value": "99999"},
                            {"label": "⚡ 直接搜→", "value": "skip"},
                        ],
                    }
                )
            if (
                guide_round < 1
                and len(groups) > 3
                and len(all_items) >= 8
                and prices
                and max(prices) / max(min(prices), 1) > 2.0
                and not has_model_num
            ):
                yield sse({"type": "progress", "msg": "🤔 帮你挑几个靠谱的～"})
                # 2026-08-11 小布：对话历史拼 prompt（LLM 看完整上下文）
                history_txt = ""
                if session_id:
                    _c = None
                    try:
                        _c = get_conn()
                        _row = _c.execute(
                            "SELECT history FROM chat_sessions WHERE session_id=? LIMIT 1",
                            (session_id,),
                        ).fetchone()
                        if _row:
                            _hist = _json.loads(_row["history"] or "[]")
                            history_txt = chr(10).join(
                                ("用户: " if m.get("role") == "user" else "AI: ")
                                + str(m.get("content", ""))[:120]
                                for m in _hist[-8:]
                            )
                    except Exception:
                        pass
                    finally:
                        if _c:
                            try:
                                _c.close()
                            except Exception:
                                pass
                options = await asyncio.to_thread(
                    generate_options, keyword, groups, history_txt
                )
                if options:
                    yield sse({"type": "guide", "options": options})

            yield step("比价合并", "done")
            yield step("内容联动", "running")
            content = await asyncio.to_thread(read_content_items, keyword)
            # v5.2 来源受限标注（购物研究助手案例）：内容数据 <5 条时诚实标注
            content_limited = len(content.get("items", [])) < 5
            subsidies = await asyncio.to_thread(find_subsidies, keyword, search_cat)
            if await _aborted():
                return
            yield step("内容联动", "done")
            yield sse(
                {
                    "type": "done",
                    "keyword": keyword,
                    "category": category,
                    "groups": groups,
                    "total": len(all_items),
                    "tb_count": len(tb_items),
                    "pdd_count": len(pdd_items),
                    "vip_count": len(vip_items),
                    "manual_count": len(manual_items),
                    "content": content,
                    "content_limited": content_limited,
                    "slow_count": len(slow_items),
                    "options": options,
                    "subsidies": subsidies,
                    "mode": "live",
                }
            )
        except Exception as e:
            yield sse({"type": "error", "msg": str(e)[:200]})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ===== 遗留入口（DEPRECATED，2026-08-13 小布🟡4）=====
# 前端已全部改走 /search_sse；此 POST /search 仅保留供直接调用/测试，
# 逻辑与 SSE 版存在分叉——新功能只改 SSE 版，本入口不再维护，后续版本删除


@router.post("/search", response_class=HTMLResponse)
def search(request: Request, keyword: str = Form(...), category: str = Form("")):
    request.state.deprecated = True  # 标记：日志/监控可识别遗留入口调用
    keyword = keyword.strip()
    if not keyword:
        return templates.TemplateResponse(
            request, "index.html", {"categories": CATEGORIES, "error": "请输入商品名称"}
        )

    # 意图解析（对话式输入支持）
    intent = parse_intent(keyword)
    keyword = intent.get("keyword") or keyword
    category = intent.get("category") or category

    init_db()
    # 双平台搜索（带缓存）
    tb_items = search_goods(keyword, category or None)
    pdd_items = search_pdd(keyword)
    all_items = tb_items + pdd_items

    # SKU 分组
    groups = []
    if category and category in ADAPTERS:
        parsed = parse_items(all_items, category)
        grouped = group_by_sku(parsed, category)
        for key, items in grouped.items():
            if not key or key == "未解析":
                continue
            by_platform: dict = {}
            for it in items:
                it["value_score"] = value_score(it)
                p = it.get("platform", "?")
                if (
                    p not in by_platform
                    or it["actualPrice"] < by_platform[p]["actualPrice"]
                ):
                    by_platform[p] = it
            best = min(by_platform.values(), key=lambda x: x["actualPrice"])
            groups.append(
                {
                    "key": key,
                    "count": len(items),
                    "platforms": sorted(
                        by_platform.values(), key=lambda x: x["actualPrice"]
                    ),
                    "best": best,
                }
            )
        groups.sort(key=lambda g: g["best"]["actualPrice"])
    else:
        for it in all_items[:20]:
            groups.append(
                {"key": it["title"][:30], "count": 1, "platforms": [it], "best": it}
            )

    # 人工录入结果合并（众包补盲区）
    manual_items = find_manual_prices(keyword)
    for m in manual_items:
        groups.append(
            {
                "key": f"人工录入: {m['title'][:20]}",
                "count": 1,
                "platforms": [
                    {
                        "platform": m["platform"],
                        "title": m["title"],
                        "actualPrice": m["price"],
                        "originalPrice": None,
                        "shopName": m["shop_name"] + "（人工录入）",
                        "url": m["url"],
                    }
                ],
                "best": None,
            }
        )

    # 存库
    with closing(get_conn()) as conn:
        for it in all_items:
            save_search_result(conn, it, category or "未分类")
            upsert_product_item(conn, it, category or "")
        conn.commit()

    # 国补/优惠标注
    subsidies = find_subsidies(keyword, category)

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "keyword": keyword,
            "category": category,
            "groups": groups[:10],
            "total": len(all_items),
            "tb_count": len(tb_items),
            "pdd_count": len(pdd_items),
            "manual_count": len(manual_items),
            "subsidies": subsidies,
        },
    )


# ========== v6 多用户（角色切换，WorkBuddy 定案：不登录，localStorage）==========
