# -*- coding: utf-8 -*-
"""S4 逻辑变化信号化（s4_monitor.py——2026-08-16 架构师 B3 落地）

现状问题：S1 止损/S2 止盈/S3 估值都信号化了——S4（逻辑变化卖出）靠人发现
（减持/暴雷公告没人看=不知道）。本模块：每日对持仓股拉巨潮官方公告 →
关键词命中 → 晨报【风险提醒】段提示 → 甲方确认后走 S4 卖出流程。

红线：
- 只提醒不自动卖（卖出必须甲方确认——半自动）
- 去重幂等（同一天同一公告只提醒一次）
- 公告接口失败不阻塞晨报（红线③）
- 弱信号（解禁）只标注不告警——控制误报

数据源：巨潮 cninfo（官方公告渠道——a-stock-data skill 7.1 适配）
"""

from __future__ import annotations

import json
import os
import time

import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
ALERTS_FILE = os.path.join(DATA_DIR, "s4_alerts.jsonl")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# 强信号（命中即提醒——逻辑变化候选）
STRONG_KEYWORDS = [
    "减持",  # 大股东/董监高减持计划/进展/完成
    "质押",  # 股权质押（高比例=风险）
    "冻结",  # 股权冻结
    "立案",  # 立案调查/侦查
    "退市",  # 退市风险警示
    "警示",  # 警示函
    "亏损",  # 业绩预亏/亏损
    "造假",  # 财务造假
    "违规",  # 违规担保/资金占用/违规减持
    "占用",  # 资金占用
    "平仓",  # 强制平仓风险
    "ST",  # 特别处理
    "预亏",  # 业绩预告亏损
]
# 弱信号（仅标注——不告警）
WEAK_KEYWORDS = ["解禁", "回购", "增持", "分红"]


def _get_org_id(code: str) -> str:
    """巨潮 orgId 动态查询（2026-08-16 实测：部分公司 99000 数字格式——gssh0 规则撞对）

    topSearch POST 返回 [{code, orgId, category}]——失败兜底旧规则
    """
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.cninfo.com.cn/",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        r = requests.post(
            "https://www.cninfo.com.cn/new/information/topSearch/query",
            data={"keyWord": code, "maxNum": 5},
            headers=headers,
            timeout=15,
        )
        for x in r.json() or []:
            if x.get("code") == code and x.get("category") == "A股":
                return x.get("orgId", "")
    except (requests.RequestException, ValueError):
        pass
    # 兜底旧规则（部分股票撞对——如中信 gssh0600030）
    if code.startswith("6"):
        return f"gssh0{code}"
    if code.startswith("8") or code.startswith("4"):
        return f"gsbj0{code}"
    return f"gssz0{code}"


def _cninfo_announcements(code: str, page_size: int = 20) -> list[dict]:
    """巨潮公告查询（orgId 动态解析——2026-08-16 修 99000 格式）"""
    org_id = _get_org_id(code)
    if not org_id:
        return []
    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    try:
        r = requests.post(
            "https://www.cninfo.com.cn/new/hisAnnouncement/query",
            data=payload,
            headers=headers,
            timeout=15,
        )
        d = r.json()
    except (requests.RequestException, ValueError):
        return []
    rows = []
    for item in d.get("announcements", []) or []:
        ts = item.get("announcementTime")
        try:
            date = (
                time.strftime("%Y-%m-%d", time.localtime(int(ts) / 1000))
                if isinstance(ts, (int, float))
                else str(ts or "")[:10]
            )
        except (TypeError, ValueError, OSError):
            date = ""
        rows.append(
            {
                "title": item.get("announcementTitle", ""),
                "date": date,
            }
        )
    return rows


def _match_keywords(title: str) -> tuple[str | None, str]:
    """标题命中判断——返回 (level, keyword)——未命中 (None, '')"""
    for kw in STRONG_KEYWORDS:
        if kw in title:
            return "strong", kw
    for kw in WEAK_KEYWORDS:
        if kw in title:
            return "weak", kw
    return None, ""


def _seen(key: str) -> bool:
    """去重：同 (code+date+title) 已提醒过？"""
    if not os.path.exists(ALERTS_FILE):
        return False
    try:
        with open(ALERTS_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("key") == key:
                        return True
                except ValueError:
                    continue
    except OSError:
        pass
    return False


def _append_alert(rec: dict) -> None:
    try:
        with open(ALERTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def scan_holdings() -> list[dict]:
    """扫描持仓股最近公告——返回新命中（未提醒过的）

    返回 [{code, name, date, title, keyword, level}]
    """
    from tools.strategy_engine import portfolio as pf

    p = pf.Portfolio()
    positions, _ = p.positions()
    out: list[dict] = []
    for pos in positions:
        code = pos.get("code", "")
        name = pos.get("name", "")
        for a in _cninfo_announcements(code):
            title = a.get("title", "")
            level, kw = _match_keywords(title)
            if not level:
                continue
            key = f"{code}|{a.get('date', '')}|{title[:40]}"
            if _seen(key):
                continue
            rec = {
                "key": key,
                "code": code,
                "name": name,
                "date": a.get("date", ""),
                "title": title[:80],
                "keyword": kw,
                "level": level,
                "ts": time.strftime("%Y-%m-%d %H:%M"),
            }
            _append_alert(rec)
            if level == "strong":
                out.append(rec)  # 弱信号只存档不提醒
    return out


def build_alert_section() -> str:
    """晨报【风险提醒】段——无命中返回空串（不占版面）"""
    hits = scan_holdings()
    if not hits:
        return ""
    lines = ["🔴 **逻辑变化监测（S4）**"]
    for h in hits:
        lines.append(
            f"  {h['name']}({h['code']}) {h['date']}: {h['title']}"
            f"（命中：{h['keyword']}——S4 卖出候选——请确认）"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sec = build_alert_section()
    print(sec if sec else "✅ 无 S4 风险公告命中")
