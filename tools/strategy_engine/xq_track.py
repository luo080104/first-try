# -*- coding: utf-8 -*-
"""雪球组合跟踪（xq_track.py——2026-08-16 大V 自动跟踪落地）

定案回顾（docs/SYNC.md 08-13 + 08-14 六轮拍板）：vpush 自动为主（雪球/微博+组合调仓）
→ 失败退手动。vpush 未部署——本地自建等价方案（更轻，无 Docker 依赖）：

流程：
  login     → Playwright 打开雪球，用户扫码登录 → cookie 存 data/xq_cookies.json
               （一次性——之后 headless 自动跑）
  resolve   → 组合名 → ZH 代码（搜索接口）→ 存 data/xq_cubes.json
  track     → 每日抓所有组合最近调仓+净值 → bigv_trades.jsonl + data/xq_nav.json
               （幂等——按组合+日期去重）
  status    → 当前跟踪状态（组合数/最近抓取/最新调仓）

合规：只抓公开可见数据（组合调仓公开可见——跟单功能本就公开）——不碰付费内容。
红线：跟踪≠跟随——数据进候选池，过观复过滤才可买（Q3）。
容错：所有文件 IO/网络调用包 try——失败不抛（红线③）。
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
COOKIE_FILE = os.path.join(DATA_DIR, "xq_cookies.json")
STATE_FILE = os.path.join(
    DATA_DIR, "xq_state.json"
)  # Playwright storage_state（cookie+localStorage——headless 复用关键）
CUBES_FILE = os.path.join(DATA_DIR, "xq_cubes.json")
NAV_FILE = os.path.join(DATA_DIR, "xq_nav.json")
TRADES_FILE = os.path.join(DATA_DIR, "bigv_trades.jsonl")
DESC_FILE = os.path.join(DATA_DIR, "xq_cube_desc.json")
POSTS_FILE = os.path.join(DATA_DIR, "xq_posts.jsonl")  # 观点型大V 发言（2026-08-17）

# 观点型大V（无公开组合——跟踪发言不跟踪组合——甲方 8/17 拍板）
POST_TRACK: dict[str, int] = {
    "陈嘉禾": 1340904670,
    "大道无形我有型": 1247347556,
    "宁静的冬日M": 1556808774,
    "czy710": 6308001210,
    "山高林茂": 7895717506,
    "爱投资的小人书": 7103876041,
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
XQ = "https://xueqiu.com"


def _load_json(path: str, default: Any = None) -> Any:
    """读 JSON——失败返回 default（不抛——红线③容错）"""
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path: str, data: Any) -> bool:
    """写 JSON——失败返回 False（不抛）"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _load_cookies() -> dict[str, str]:
    return _load_json(COOKIE_FILE, {}) or {}


def _api_get(path: str, params: dict | None = None) -> dict | None:
    """带 cookie 调雪球 API——失败返回 None（不抛——红线③容错）"""
    cookies = _load_cookies()
    if not cookies:
        return None
    try:
        r = requests.get(
            f"{XQ}{path}",
            params=params,
            headers={"User-Agent": UA, "Referer": XQ},
            cookies=cookies,
            timeout=15,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def login() -> bool:
    """Playwright 打开雪球主页——用户扫码/密码登录——保存完整 storage_state

    返回是否拿到有效登录态（xq_a_token）
    """
    from playwright.sync_api import (
        sync_playwright,  # 函数内导入（懒加载——装不上不影响其他功能）
    )

    print("⏳ 打开雪球浏览器窗口——请在弹出的浏览器里完成登录（扫码/密码均可）")
    print("   登录成功后本脚本自动抓取登录态——看到『✅ 登录态已保存』即可关浏览器")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False, channel=None)
            ctx = browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.goto(XQ, timeout=30000)
            # 轮询等待登录态出现（最长 180 秒）
            for _ in range(180):
                cookies = ctx.cookies()
                c = {x.get("name", ""): x.get("value", "") for x in cookies}
                if c.get("xq_a_token"):
                    ctx.storage_state(
                        path=STATE_FILE
                    )  # 完整状态（cookie+localStorage）
                    _write_json(COOKIE_FILE, c)  # 兼容 requests 直调
                    browser.close()
                    print("✅ 登录态已保存 → data/xq_state.json")
                    return True
                time.sleep(1)
            browser.close()
            print("⚠️ 超时未检测到登录态（180 秒）——重试")
            return False
    except Exception:
        print(
            "⚠️ 浏览器启动失败（playwright 未装？）——python -m playwright install chromium"
        )
        return False


def resolve_cubes() -> dict[str, dict]:
    """大V → uid → 组合列表（真实接口——2026-08-16 实测打通）

    链路：suggest.json?q=大V名 → uid → cubes/list.json?user_id= → 组合
    （含 active_flag 活跃标记——解决组合关停验证）
    存 data/xq_cubes.json：{大V名: {symbol, name, active, net_value, total_gain, last_rb_id}}
    """
    import yaml

    list_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "bigv_list.yaml"
    )
    try:
        with open(list_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        print("⚠️ bigv_list.yaml 读取失败")
        return {}

    cookies = _load_cookies()
    if not cookies:
        print("⚠️ 无登录态——先跑: python -m tools.strategy_engine.xq_track login")
        return {}

    out: dict[str, dict] = {}
    bigvs = [b["name"] for b in cfg.get("bigvs", []) if b.get("platform")]
    for bigv in bigvs:
        if bigv in out:
            continue
        try:
            r = requests.get(
                f"{XQ}/query/v1/suggest.json",
                params={"q": bigv, "type": 0},
                headers={"User-Agent": UA, "Referer": XQ},
                cookies=cookies,
                timeout=15,
            )
            if r.status_code != 200:
                time.sleep(0.5)
                continue
            hits = [d for d in r.json().get("data", []) if d.get("query") == bigv]
            if not hits:
                time.sleep(0.5)
                continue
            uid = hits[0]["uid"]
            r2 = requests.get(
                f"{XQ}/cubes/list.json",
                params={"user_id": uid, "count": 50},
                headers={"User-Agent": UA, "Referer": XQ},
                cookies=cookies,
                timeout=15,
            )
            if r2.status_code == 200:
                cubes = r2.json().get("list", [])
                if cubes:
                    top = cubes[0]
                    out[bigv] = {
                        "uid": uid,
                        "symbol": top["symbol"],
                        "name": top["name"],
                        "active": top.get("active_flag", False),
                        "net_value": top.get("net_value"),
                        "total_gain": top.get("total_gain"),
                        "last_rb_id": top.get("last_rb_id"),
                        "n_cubes": len(cubes),
                    }
                    print(
                        f"  ✅ {bigv}: {top['name']} {top['symbol']} "
                        f"{'🟢' if top.get('active_flag') else '⚪ 已停'}"
                        f" 净值{top.get('net_value')} 总收益{top.get('total_gain')}%"
                    )
                else:
                    print(f"  ⚪ {bigv}: 无组合")
            time.sleep(0.8)  # 节流（雪球 WAF——08-11 教训）
        except (requests.RequestException, ValueError, KeyError):
            time.sleep(0.5)
            continue
    _write_json(CUBES_FILE, out)
    n_active = sum(1 for v in out.values() if v.get("active"))
    print(f"📌 解析完成: {len(out)}/{len(bigvs)} 大V——活跃组合 {n_active} 个")
    return out


def track() -> dict[str, int]:
    """每日抓取：活跃组合净值刷新 + last_rb_id 变化 → 调仓明细

    幂等：同一组合+同一股票+同日期不重复写。返回 {resolved, tracked, new_trades}
    """
    cubes: dict[str, dict] = _load_json(CUBES_FILE, {}) or {}
    if not cubes:
        print("⚠️ 无组合映射——先跑: python -m tools.strategy_engine.xq_track resolve")
        return {}
    navs: dict[str, dict] = _load_json(NAV_FILE, {}) or {}
    new_trades = 0
    cookies = _load_cookies()
    for name, info in cubes.items():
        symbol = info.get("symbol", "")
        if not symbol:
            continue
        # ① 刷新组合状态（净值/收益/最新调仓锚点）
        try:
            r = requests.get(
                f"{XQ}/cubes/list.json",
                params={"user_id": info["uid"], "count": 50},
                headers={"User-Agent": UA, "Referer": XQ},
                cookies=cookies,
                timeout=15,
            )
            if r.status_code == 200:
                fresh = next(
                    (x for x in r.json().get("list", []) if x.get("symbol") == symbol),
                    None,
                )
                if fresh:
                    info.update(
                        {
                            "active": fresh.get("active_flag", False),
                            "net_value": fresh.get("net_value"),
                            "total_gain": fresh.get("total_gain"),
                            "last_rb_id": fresh.get("last_rb_id"),
                        }
                    )
                    navs[name] = {
                        "symbol": symbol,
                        "name": fresh.get("name"),
                        "nav": fresh.get("net_value"),
                        "gain": fresh.get("total_gain"),
                        "ts": time.strftime("%Y-%m-%d %H:%M"),
                    }
        except (requests.RequestException, ValueError, KeyError):
            pass
        time.sleep(2.0)  # 节流（WAF 实测：2s 间隔 15/15 通过——0.6s 时第 6 个起 400）
        # ② 调仓明细（last_rb_id 变化才拉——show_origin 实测 200）
        rb_id = info.get("last_rb_id")
        if info.get("active") and rb_id and rb_id != info.get("_last_pulled_rb"):
            try:
                r2 = requests.get(
                    f"{XQ}/cubes/rebalancing/show_origin.json",
                    params={"rb_id": rb_id},
                    headers={"User-Agent": UA, "Referer": XQ},
                    cookies=cookies,
                    timeout=15,
                )
                if r2.status_code == 200:
                    reb = r2.json().get("rebalancing") or {}
                    # created_at 是毫秒时间戳 → 转日期（1472520654 → 2016-08-30）
                    try:
                        ts_date = time.strftime(
                            "%Y-%m-%d",
                            time.localtime(int(reb.get("created_at", 0)) / 1000),
                        )
                    except (TypeError, ValueError, OSError):
                        ts_date = time.strftime("%Y-%m-%d")
                    for h in reb.get("rebalancing_histories") or []:
                        try:
                            w = float(h.get("weight") or 0)
                            pw = float(h.get("prev_weight") or 0)
                            # 买/卖判定：weight vs prev_weight（新买 prev=0 → 买）
                            if w > pw and h.get("proactive"):
                                act = "买"
                            elif w < pw and h.get("proactive"):
                                act = "卖"
                            else:
                                continue  # 系统再平衡/无变化——不记
                            ev = {
                                "ts": ts_date,
                                "bigv": name,
                                "code": h.get("stock_name") or "",
                                "action": act,
                                "weight": w,
                                "price": h.get("price"),
                                "reason": f"组合调仓（{reb.get('category', '')}）",
                            }
                        except (TypeError, ValueError):
                            continue
                        if _append_trade_if_new(ev):
                            new_trades += 1
                    info["_last_pulled_rb"] = rb_id
            except (requests.RequestException, ValueError):
                pass
            time.sleep(0.8)  # 节流
    _write_json(CUBES_FILE, cubes)
    _write_json(NAV_FILE, navs)
    # ③ 观点型大V 发言（2026-08-17——甲方：不要局限于组合——无组合大V 跟踪发言）
    try:
        posts = fetch_posts()
    except Exception:
        posts = {}  # 发言抓取失败不阻塞（红线③容错）
    n_active = sum(1 for v in cubes.values() if v.get("active"))
    return {
        "resolved": len(cubes),
        "active": n_active,
        "tracked": len(navs),
        "new_trades": new_trades,
        "new_posts": posts.get("new", 0),
    }


def _append_trade_if_new(ev: dict) -> bool:
    """按 (bigv, code, ts, action) 去重追加——返回是否新增"""
    seen: set[tuple] = set()
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        t = json.loads(line)
                        seen.add(
                            (t.get("bigv"), t.get("code"), t.get("ts"), t.get("action"))
                        )
                    except ValueError:
                        continue
        except OSError:
            pass
    key = (ev["bigv"], ev["code"], ev["ts"], ev["action"])
    if key in seen or not ev["code"]:
        return False
    try:
        with open(TRADES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def trust_level(bigv: str, desc: str, last_trade_ts: str | None) -> dict:
    """实盘贴近度分级（2026-08-16 架构师 C2 落地——三指标：自述/调仓活跃）

    返回 {level: 高|中|低, score, reasons}——供周报大V 段过滤/显示
    只做观测分级——不参与交易决策（红线：跟踪≠跟随）
    """
    import datetime as _dt

    score = 50
    reasons: list[str] = []
    d = desc or ""
    # ① 自述关键词（组合 description——虚拟 vs 实盘声明）
    for kw in [
        "虚拟",
        "并非实盘",
        "没精力",
        "不必当真",
        "测试",
        "模拟",
        "欢乐豆",
        "暂无投资建议",
        "新手",
    ]:
        if kw in d:
            score -= 25
            reasons.append(f"自述虚拟/娱乐（{kw}）")
    for kw in ["实盘", "近似", "贴近", "匹配"]:
        if kw in d:
            score += 25
            reasons.append(f"自述实盘（{kw}）")
    # ② 调仓活跃度（最近调仓距今——>180 天停更嫌疑）
    if last_trade_ts:
        try:
            days = (_dt.date.today() - _dt.date.fromisoformat(last_trade_ts)).days
        except ValueError:
            days = -1
        if days > 180:
            score -= 20
            reasons.append(f"{days} 天无调仓记录")
        elif 0 <= days < 30:
            score += 10
            reasons.append("近期调仓活跃")
    level = "高" if score >= 70 else ("中" if score >= 45 else "低")
    return {"level": level, "score": score, "reasons": reasons}


def _latest_trade_ts(bigv: str) -> str | None:
    """某大V 最近一次调仓日期（bigv_trades.jsonl）"""
    latest: str | None = None
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        t = json.loads(line)
                        if t.get("bigv") == bigv and t.get("ts"):
                            latest = max(latest or "", str(t["ts"])[:10])
                    except ValueError:
                        continue
        except OSError:
            pass
    return latest


def _clean_html(s: str) -> str:
    """清洗雪球发言 HTML（<a>xxx</a> → xxx——实体解码）"""
    import re as _re

    s = _re.sub(r"<[^>]+>", "", s or "")
    for ent, rep in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")]:
        s = s.replace(ent, rep)
    return s.strip()


def _append_posts(rec: dict) -> bool:
    """发言去重追加（按 status id——幂等）"""
    seen = set()
    if os.path.exists(POSTS_FILE):
        try:
            with open(POSTS_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        seen.add(json.loads(line)["id"])
                    except (ValueError, KeyError):
                        continue
        except OSError:
            pass
    if str(rec.get("id", "")) in seen:
        return False
    try:
        with open(POSTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def fetch_posts(count: int = 20) -> dict:
    """观点型大V 发言抓取（2026-08-17——甲方：不要局限于组合）

    无公开组合的大V（陈嘉禾/段永平等）价值在发言——每日拉最新
    存 xq_posts.jsonl（幂等按 id）——周报【大V 观点】段数据源
    """
    cookies = _load_cookies()
    if not cookies:
        return {"error": "无登录态"}
    got = new = 0
    for name, uid in POST_TRACK.items():
        try:
            r = requests.get(
                f"{XQ}/statuses/user_timeline.json",
                params={"user_id": uid, "page": 1, "count": count},
                headers={"User-Agent": UA, "Referer": XQ},
                cookies=cookies,
                timeout=15,
            )
            if r.status_code != 200:
                continue
            for st in r.json().get("statuses", []):
                rt = st.get("retweeted_status") or {}
                try:
                    ts = time.strftime(
                        "%Y-%m-%d", time.localtime(int(st.get("created_at", 0)) / 1000)
                    )
                except (TypeError, ValueError, OSError):
                    ts = ""
                rec = {
                    "id": str(st.get("id", "")),
                    "bigv": name,
                    "ts": ts,
                    # 清洗 HTML 标签（回复链接 <a>xxx</a> → xxx）
                    "text": _clean_html((st.get("text") or ""))[:400].replace("\n", " "),
                    "retweeted": bool(rt),
                    "retweet_text": (_clean_html(rt.get("text") or "")[:200] if rt else ""),
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                }
                got += 1
                if _append_posts(rec):
                    new += 1
            time.sleep(2.0)  # WAF 节流（实测 2s 安全）
        except (requests.RequestException, ValueError):
            continue
    return {"got": got, "new": new, "tracked": len(POST_TRACK)}


def status() -> str:
    """当前跟踪状态摘要（含实盘贴近度分级统计——2026-08-16）"""
    cubes: dict = _load_json(CUBES_FILE, {}) or {}
    navs: dict = _load_json(NAV_FILE, {}) or {}
    n_trades = 0
    if os.path.exists(TRADES_FILE):
        try:
            n_trades = sum(1 for _ in open(TRADES_FILE, encoding="utf-8"))
        except OSError:
            pass
    # 贴近度分级统计
    descs: dict = _load_json(DESC_FILE, {}) or {}
    levels = {"高": 0, "中": 0, "低": 0}
    for name, info in cubes.items():
        d = descs.get(name, {}).get("desc", "")
        t = trust_level(name, d, _latest_trade_ts(name))
        levels[t["level"]] = levels.get(t["level"], 0) + 1
    return (
        f"组合映射 {len(cubes)} 个 | 净值跟踪 {len(navs)} 个 | 调仓记录 {n_trades} 条 | "
        f"贴近度 高{levels['高']}/中{levels['中']}/低{levels['低']} | "
        f"登录态 {'✅' if _load_cookies() else '❌ 未登录'}"
    )


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "login":
        login()
    elif cmd == "resolve":
        resolve_cubes()
    elif cmd == "track":
        r = track()
        print(f"✅ 抓取完成: {r}")
    else:
        print(status())
        print("用法: login | resolve | track | status")


if __name__ == "__main__":
    main()
