"""虚拟盘模块（M2——事件日志+记账——Q11 前向账本的数据来源）

定案依据（docs/观复落地实施方案.md）：
- 事件流记账（dsh 事件日志设计——data/portfolio_events.jsonl——全操作可追溯）
- track 字段（Q16：base=底仓逻辑止损 / swing=波段技术止损）
- 建仓规则 P1（个股≤10% 仓位 / 行业≤25%）
- Q4：持仓 3-5 只集中（分散交给资产类别）
- Q5：现金纪律（现金 10-15%——回撤减半的防守）
- Q13：抄底网格（跌 3/6/10% 加仓——两批间隔≥4 周——加仓事件带 grid 批号）

参数均为 v0 先验（Q11 参数学习化——虚拟盘积累数据后网格搜索校准）。

运行方式：
    python -m tools.strategy_engine.portfolio buy 600036 38.46 1300 base "原因"
    python -m tools.strategy_engine.portfolio sell 600036 1300 39.5 "原因"
    python -m tools.strategy_engine.portfolio summary
"""

import json
import os
import sys
from datetime import datetime

# ---- 配置（v0 先验——Q11 待校准）----
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
PORTFOLIO_FILE = os.path.join(DATA_DIR, "portfolio.json")
EVENTS_FILE = os.path.join(DATA_DIR, "portfolio_events.jsonl")
INIT_CASH = 80000  # 虚拟盘初始资金 8 万（2026-08-16 甲方定：实盘用 8 万——虚拟盘对齐）
MAX_POSITION_PCT = 0.10  # P1：单只个股 ≤10% 仓位
MAX_INDUSTRY_PCT = 0.25  # P1：行业 ≤25%
MIN_HOLDINGS = 3  # Q4：3-5 只集中
MAX_HOLDINGS = 5
MIN_CASH_PCT = 0.10  # Q5：现金 10-15%
MAX_CASH_PCT = 0.15
GRID_STEPS = (0.03, 0.06, 0.10)  # Q13：跌 3/6/10% 加仓
GRID_MIN_INTERVAL_DAYS = 28  # Q13：两批间隔 ≥4 周（防阴跌接飞刀）


class Portfolio:
    def __init__(self, path=PORTFOLIO_FILE):
        self.path = path
        # 事件日志跟随实例账本路径（测试用临时文件时不污染真实事件流——2026-08-15 修复）
        self.events_file = (
            os.path.join(os.path.dirname(path), "portfolio_events.jsonl")
            if path != PORTFOLIO_FILE
            else EVENTS_FILE
        )
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[portfolio] 账本损坏，重新初始化: {e}")
        return {
            "init_cash": INIT_CASH,
            "cash": INIT_CASH,
            "holdings": {},
            "track": {"base": 0.0, "swing": 0.0},  # Q16 轨道累计投入（buy 时累加）
        }

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)  # 原子替换——写一半崩溃不损坏原账本
        except OSError as e:
            print(f"[portfolio] 保存失败: {e}")

    def _event(self, action, **fields):
        ev = {"ts": datetime.now().isoformat(timespec="seconds"), "action": action}
        ev.update(fields)
        try:
            os.makedirs(os.path.dirname(self.events_file), exist_ok=True)
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"[portfolio] 事件日志写入失败: {e}")

    # ---- 操作 ----
    def buy(self, code, price, shares, track="base", reason="", name="", grid=None, force=False):
        """建仓/加仓——扣现金+记持仓+事件日志。track: base(底仓)/swing(波段)

        force=True：显式越过集中度约束（人工拍板——reason 需注明 OVERRIDE——2026-08-17 审核 F1）
        """
        if price <= 0 or shares <= 0 or not isinstance(shares, int):
            return (
                False,
                f"参数无效（price={price} shares={shares}——需价格>0 且股数为正整数）",
            )
        cost = round(price * shares, 2)
        if cost > self.data["cash"]:
            return False, f"现金不足（需要 {cost}——现有 {self.data['cash']}）"
        # F1 硬约束（2026-08-17 全面审核：集中度纪律被半自动架空——超限拒绝）
        if not force:
            issues = self.check_constraints(code, price, shares)
            if issues:
                return False, "约束未过：" + "; ".join(issues)
        h = self.data["holdings"].get(code)
        if h:
            total = h["shares"] + shares
            h["avg_cost"] = round((h["avg_cost"] * h["shares"] + cost) / total, 3)
            h["shares"] = total
        else:
            self.data["holdings"][code] = {
                "code": code,
                "name": name,
                "shares": shares,
                "avg_cost": round(price, 3),
                "track": track,
                "buy_date": datetime.now().strftime("%Y-%m-%d"),
            }
        self.data["cash"] = round(self.data["cash"] - cost, 2)
        # track 累计投入（Q16 底仓/波段分轨统计——test_track_accounting 保护）
        self.data["track"][track] = round(self.data["track"].get(track, 0) + cost, 2)
        self.save()
        self._event(
            "buy",
            code=code,
            name=name,
            price=price,
            shares=shares,
            track=track,
            reason=reason,
            grid=grid,
            cash_after=self.data["cash"],
        )
        return True, f"已建仓 {code} {shares} 股 @ {price}（{track}）"

    def sell(self, code, shares, price, reason=""):
        """卖出——回现金+减持仓+事件日志"""
        if price <= 0 or shares <= 0 or not isinstance(shares, int):
            return (
                False,
                f"参数无效（price={price} shares={shares}——需价格>0 且股数为正整数）",
            )
        h = self.data["holdings"].get(code)
        if not h:
            return False, f"无持仓 {code}"
        if shares > h["shares"]:
            return False, f"持仓不足（持有 {h['shares']}——想卖 {shares}）"
        proceeds = round(price * shares, 2)
        h["shares"] -= shares
        if h["shares"] == 0:
            del self.data["holdings"][code]
        self.data["cash"] = round(self.data["cash"] + proceeds, 2)
        self.save()
        # 失败票黑名单（书 L2540——2026-08-17：卖出即记——买回前检查）
        try:
            from tools.strategy_engine.failed_pool import record_sell

            record_sell(code, h.get("name", ""), price, reason)
        except Exception:
            pass  # 黑名单记录失败不阻塞卖出（容错红线）
        self._event(
            "sell",
            code=code,
            name=h.get("name", ""),
            price=price,
            shares=shares,
            track=h.get("track", "base"),
            reason=reason,
            cash_after=self.data["cash"],
        )
        return True, f"已卖出 {code} {shares} 股 @ {price}"

    # ---- 查询 ----
    def positions(self, quotes=None):
        """持仓明细（quotes: {code: price}——市值/盈亏）"""
        out = []
        total = self.data["cash"]
        for code, h in self.data["holdings"].items():
            px = (quotes or {}).get(code, h["avg_cost"])
            market = round(px * h["shares"], 2)
            pnl = round(market - h["avg_cost"] * h["shares"], 2)
            out.append(
                {
                    "code": code,
                    "name": h["name"],
                    "shares": h["shares"],
                    "avg_cost": h["avg_cost"],
                    "price": px,
                    "market": market,
                    "pnl": pnl,
                    "pnl_pct": round(pnl / (h["avg_cost"] * h["shares"]) * 100, 2)
                    if h["avg_cost"]
                    else 0,
                    "track": h["track"],
                }
            )
            total += market
        return out, round(total, 2)

    def summary(self, quotes=None):
        """总览：总资产/现金/持仓数/权重/现金比例/约束检查

        附带：equity_curve 净值记录（每日收盘调用——gate_check'4 周跑赢'数据基础）
        """
        positions, total = self.positions(quotes)
        cash_pct = round(self.data["cash"] / total * 100, 1) if total else 0
        cash_ok = MIN_CASH_PCT <= cash_pct <= MAX_CASH_PCT
        return {
            "total": total,
            "cash": self.data["cash"],
            "cash_pct": cash_pct,
            "cash_ok": cash_ok,
            "n_holdings": len(positions),
            "positions": positions,
            "init_cash": self.data.get("init_cash", INIT_CASH),
        }

    def record_equity(self, quotes=None) -> float:
        """记录当日净值点（equity_curve——WealthAgent paper_trader 借鉴）

        每日收盘调用：总资产 → 追加到 equity_curve（日期/总资产）——gate_check 用
        同一日重复调用不重复记录（幂等）
        """
        _, total = self.positions(quotes)
        curve = self.data.setdefault("equity_curve", [])
        today = datetime.now().strftime("%Y-%m-%d")
        if curve and curve[-1].get("date") == today:
            curve[-1]["total"] = round(total, 2)  # 当日覆盖（盘中多次调用取最新）
        else:
            curve.append({"date": today, "total": round(total, 2)})
        self.save()
        return total

    def equity_series(self) -> list[dict]:
        """净值序列（date/total 列表——空仓也有值）——gate_check/周报用"""
        return list(self.data.get("equity_curve", []))

    # ---- 约束检查（P1/Q4/Q5——买入前检查）----
    def check_constraints(self, code, price, shares, total=None):
        """返回违规列表（空=合规）。P1 个股≤10% / Q4 3-5 只 / Q5 现金底线"""
        issues = []
        _, cur_total = self.positions()
        total = total or (cur_total + price * shares)
        # P1：单只 ≤10%（含本次买入后）
        held_cost = self.data["holdings"].get(code, {}).get("avg_cost", 0) * self.data[
            "holdings"
        ].get(code, {}).get("shares", 0)
        new_pct = (held_cost + price * shares) / total * 100
        if new_pct > MAX_POSITION_PCT * 100:
            issues.append(f"P1 单只超限：{code} 将占 {new_pct:.1f}%（上限 10%）")
        # Q4：3-5 只（新开仓时检查数量）
        if (
            code not in self.data["holdings"]
            and len(self.data["holdings"]) >= MAX_HOLDINGS
        ):
            issues.append(
                f"Q4 持仓数超限：已有 {len(self.data['holdings'])} 只（上限 5）"
            )
        # Q5：买入后现金不得低于 10%
        new_cash = self.data["cash"] - price * shares
        if total > 0 and new_cash / total < MIN_CASH_PCT:
            issues.append(
                f"Q5 现金纪律：买入后现金 {new_cash / total * 100:.1f}%（底线 10%）"
            )
        # Q6 行业聚合 ≤25%（2026-08-17 审核 F1：金融 52% 超 2 倍——补行业约束）
        try:
            from tools.strategy_engine.industry import industry_of

            cat = None
            ind = industry_of(code)
            if ind:
                cat = ind.get("category")
            if cat:
                # 买入后行业总市值占比（按持仓成本+本次买入估算）
                sector_cost = sum(
                    h["avg_cost"] * h["shares"]
                    for c, h in self.data["holdings"].items()
                    if c != code
                    and (industry_of(c) or {}).get("category") == cat
                )
                sector_cost += held_cost + price * shares
                sector_pct = sector_cost / total * 100 if total else 0
                if sector_pct > 25:
                    issues.append(
                        f"行业聚合超限：{cat} 类将占 {sector_pct:.1f}%（上限 25%）"
                    )
        except Exception:
            pass  # 行业分类失败不阻塞（行业约束为辅助——P1/Q5 仍是主约束）
        return issues


def _get_quotes(codes):
    """取实时价格（腾讯行情——复用 data.py）"""
    from tools.strategy_engine import data

    quotes = {}
    try:
        res = data.tencent_quote(codes)
        for code, q in res.items():
            quotes[code] = q.get("price") or 0
    except Exception:
        pass  # 行情失败不阻塞记账（用成本价估值）
    return quotes


def main():
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
        pf = Portfolio()
        if cmd == "buy" and len(sys.argv) >= 6:
            code, price, shares, track = (
                sys.argv[2],
                float(sys.argv[3]),
                int(sys.argv[4]),
                sys.argv[5],
            )
            reason = sys.argv[6] if len(sys.argv) > 6 else ""
            issues = pf.check_constraints(code, price, shares)
            if issues:
                print("⚠️ 约束检查未过：")
                for i in issues:
                    print(f"  - {i}")
                print("（不阻止——记录事件供确认——半自动红线：人确认后执行）")
            _, msg = pf.buy(code, price, shares, track=track, reason=reason)
            print(msg)
        elif cmd == "sell" and len(sys.argv) >= 5:
            code, shares, price = sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
            reason = sys.argv[5] if len(sys.argv) > 5 else ""
            _, msg = pf.sell(code, shares, price, reason=reason)
            print(msg)
        elif cmd == "summary":
            s = pf.summary(_get_quotes(list(pf.data["holdings"].keys())))
            print(
                f"总资产 {s['total']} | 现金 {s['cash']}（{s['cash_pct']}%）"
                f"{'✅' if s['cash_ok'] else '⚠️'} | 持仓 {s['n_holdings']} 只"
            )
            for p in s["positions"]:
                print(
                    f"  {p['name'] or p['code']}({p['code']}) {p['shares']}股 @ {p['avg_cost']}"
                    f" 现价 {p['price']} 盈亏 {p['pnl']:+.0f} ({p['pnl_pct']:+.1f}%) [{p['track']}]"
                )
            print(f"底仓/波段投入: {pf.data['track']}")
        else:
            print(__doc__)
    except (IndexError, ValueError) as e:
        print(f"参数错误: {e}")
        print(__doc__)


if __name__ == "__main__":
    main()
