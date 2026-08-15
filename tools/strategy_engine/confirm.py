# -*- coding: utf-8 -*-
"""确认交互（半自动灵魂——老师红线①：不做实盘自动决策）

流程：core_loop 达标信号 → append_pending（待确认队列）→ 用户确认（1/2/3）：
    1 = 确认（执行买入——入虚拟盘记账 + signal_ledger 记录）
    2 = 修改（输入价格/股数再确认）
    3 = 忽略（记录事件——不执行——同样入账本供诊断）

MVP：控制台交互（企业微信推送 = M3 vpush 阶段后接）。
默认股数 = P1 上限 10% 仓位 ÷ 现价（取整百——v0 先验——Q13 网格分批后接）。

运行：python -m tools.strategy_engine.confirm
"""

import json
import os
import sys
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
PENDING_FILE = os.path.join(DATA_DIR, "pending_trades.json")
MAX_POSITION_PCT = 0.10  # P1：单只 ≤10% 仓位（默认股数估算——v0）


def _load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_pending(items):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[confirm] 队列保存失败: {e}")


def append_pending(signal, total_assets=None):
    """core_loop 达标信号入队（同 code 已有 pending 不重复——去重）"""
    items = _load_pending()
    if any(i["code"] == signal["code"] and i.get("status") == "pending" for i in items):
        return False, f"{signal['code']} 已在待确认队列"
    assets = total_assets or 100000  # 虚拟盘初始 10 万（v0）
    try:
        shares = int(assets * MAX_POSITION_PCT / signal["price"] // 100 * 100) or 100
    except (KeyError, TypeError, ZeroDivisionError, ValueError):
        shares = 100  # 价格异常 → 安全降级（红线③容错）
    item = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "code": signal["code"],
        "name": signal.get("name", ""),
        "price": round(signal["price"], 2),
        "shares": shares,
        "score": signal.get("score"),
        "threshold": signal.get("threshold"),
        "track": signal.get("track", "base"),
        "reason": signal.get("reason", "Q12 打分达标"),
        "status": "pending",
    }
    items.append(item)
    _save_pending(items)
    return (
        True,
        f"{signal['name'] or signal['code']} 已入待确认队列（{shares} 股 @ {item['price']}）",
    )


def list_pending():
    return [i for i in _load_pending() if i.get("status") == "pending"]


def confirm_loop():
    """交互确认：1 确认 / 2 修改 / 3 忽略 / q 退出"""
    pending = list_pending()
    if not pending:
        print("无待确认信号——今天没有达标候选？")
        return
    for i, item in enumerate(pending, 1):
        tag = (
            f"{item['score']}分（门槛 {item['threshold']}）"
            if item.get("score") is not None
            else "B3战术信号（回测达标）"
        )
        print(f"\n[{i}] 🔔 {item['name']}({item['code']}) {tag}")
        print(
            f"    建议: {item['shares']} 股 @ {item['price']} "
            f"[{item['track']}] 原因: {item['reason']}"
        )
        choice = input("    1=确认买  2=改价格/股数  3=忽略  q=退出: ").strip()
        if choice == "q":
            break
        if choice == "1":
            _execute(item)
        elif choice == "2":
            try:
                new_price = float(input("    新价格: ").strip() or item["price"])
                new_shares = int(input("    新股数: ").strip() or item["shares"])
                item["price"], item["shares"] = new_price, new_shares
                _execute(item)
            except ValueError as e:
                print(f"    输入无效: {e}——跳过")
        elif choice == "3":
            _ignore(item)
        else:
            print("    无效输入——跳过（可后续再确认）")


def _execute(item):
    """确认执行：虚拟盘买入 + 账本记录 + 队列状态更新"""
    from tools.strategy_engine import portfolio as pf
    from tools.strategy_engine import signal_ledger as sl

    p = pf.Portfolio()
    ok, msg = p.buy(
        item["code"],
        item["price"],
        item["shares"],
        track=item["track"],
        reason=item["reason"],
        name=item["name"],
    )
    if ok:
        sl.record(
            item["code"],
            name=item["name"],
            sig_type="score_pass",
            price=item["price"],
            reason=item["reason"],
            track=item["track"],
            threshold=item.get("threshold"),
        )
        item["status"] = "confirmed"
        print(f"    ✅ {msg}")
    else:
        print(f"    ⚠️ {msg}")
    _save_pending(_load_pending())


def _ignore(item):
    from tools.strategy_engine import signal_ledger as sl

    sl.record(
        item["code"],
        name=item["name"],
        sig_type="score_pass",
        price=item["price"],
        reason=item["reason"] + "（人工忽略）",
        track=item["track"],
    )
    item["status"] = "ignored"
    _save_pending(_load_pending())
    print(f"    已忽略 {item['name']}（事件已记——供行为诊断）")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for i in list_pending():
            print(
                f"  {i['name']}({i['code']}) {i['shares']}股 @ {i['price']} [{i['status']}]"
            )
    else:
        confirm_loop()


if __name__ == "__main__":
    main()
