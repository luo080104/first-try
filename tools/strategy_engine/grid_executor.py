# -*- coding: utf-8 -*-
"""抄底执行器（Q13/Q18——左侧价格网格——portfolio grid 字段联动）

定案（docs/观复落地实施方案.md Q13/Q18）：
- 跌 3%/6%/10% 分批加仓（相对首仓价——+9.9% vs 一次性 +6.6%——6 次样本）
- 两批间隔 ≥4 周（时间保险——防阴跌接飞刀）
- 触发 → 建议入待确认队列（半自动——confirm 1确认/2改/3忽略——红线）
- 右侧确认降级为"网格停止加仓"条件（"左侧买、右侧停"——Q18）

参数 v0 先验（Q11 校准清单）。运行：python -m tools.strategy_engine.grid_executor
"""

import json
import os
from datetime import datetime

from tools.strategy_engine import data
from tools.strategy_engine import portfolio as pf

GRID_STEPS = (0.03, 0.06, 0.10)  # Q13：跌 3/6/10%
GRID_MIN_INTERVAL_DAYS = 28  # Q13：两批间隔 ≥4 周
GRID_STATE_FILE = os.path.join(pf.DATA_DIR, "grid_state.json")
GRID_ADD_PCT = 0.05  # v0：每批加仓 = 组合 5% 仓位（Q11 待校准）


def _load_state():
    if os.path.exists(GRID_STATE_FILE):
        try:
            with open(GRID_STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state):
    try:
        os.makedirs(pf.DATA_DIR, exist_ok=True)
        with open(GRID_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[grid] 状态保存失败: {e}")


def register_position(code, base_price):
    """建仓时登记网格基准（首仓价——触发判定基准）"""
    state = _load_state()
    state[code] = {"base": base_price, "triggered": [], "last_add": None}
    _save_state(state)
    return state[code]


def check_grid(code, price, total_assets=pf.INIT_CASH):
    """检查单个持仓的网格触发——返回触发的批次建议（未触发返回 None）"""
    state = _load_state()
    st = state.get(code)
    if not st:
        return None
    base = st["base"]
    # 时间保险：距上次加仓 <4 周 → 不触发（防阴跌接飞刀）
    if st.get("last_add"):
        try:
            days = (datetime.now() - datetime.strptime(st["last_add"], "%Y-%m-%d")).days
            if days < GRID_MIN_INTERVAL_DAYS:
                return None
        except ValueError:
            pass
    # 找第一个未触发的批次（价格到位）
    for i, step in enumerate(GRID_STEPS, 1):
        if i in st["triggered"]:
            continue
        if price <= base * (1 - step):
            try:
                shares = int(total_assets * GRID_ADD_PCT / price // 100 * 100) or 100
            except (TypeError, ValueError):
                shares = 100  # 异常兜底——默认一手（pi-lens 红线：int() 需 try）
            return {
                "code": code,
                "grid": i,
                "step_pct": step * 100,
                "target_price": round(base * (1 - step), 2),
                "price": price,
                "shares": shares,
                "reason": f"网格第{i}批（跌{step * 100:.0f}%——左侧加仓）",
            }
    return None


def run_check(quotes=None):
    """对所有持仓跑网格检查——触发→入待确认队列（半自动）"""
    from tools.strategy_engine import confirm as cf

    p = pf.Portfolio()
    items = []
    for code in p.data["holdings"]:
        px = None
        if quotes:
            px = quotes.get(code)
        else:
            try:
                q = data.tencent_quote([code])
                px = (q.get(code) or {}).get("price")
            except Exception:
                pass
        if not px:
            continue
        hit = check_grid(code, px)
        if hit:
            items.append(hit)
            cf.append_pending(
                {
                    **hit,
                    "name": p.data["holdings"][code].get("name", ""),
                    "track": "swing",
                }
            )  # 网格加仓归波段仓（Q16）
    return items


def mark_triggered(code, grid_no, add_date=None):
    """确认执行后标记批次已触发（confirm._execute 联动）"""
    state = _load_state()
    st = state.get(code)
    if st and grid_no not in st["triggered"]:
        st["triggered"].append(grid_no)
        st["last_add"] = add_date or datetime.now().strftime("%Y-%m-%d")
        _save_state(state)


def main():
    hits = run_check()
    if hits:
        print(f"网格触发 {len(hits)} 个（已入待确认队列——跑 confirm 确认）:")
        for h in hits:
            print(
                f"  {h['code']} 第{h['grid']}批 {h['shares']}股 @ {h['price']}（跌{h['step_pct']:.0f}%）"
            )
    else:
        print("无网格触发（价格未到位或间隔不足 4 周）")


if __name__ == "__main__":
    main()
