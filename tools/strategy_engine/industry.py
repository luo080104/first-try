"""行业面打分（书 L3098"选股票一定是先选行业"——2026-08-17 实现）

行业面 20 分 = 格局 8（静态档案——集中度/龙头差距——书框架人工评级）
             + 位置 6（当前行业 PE 横向分 + 2 年涨幅防接盘——书 N10 精神）
             + 周期 4（3 年波动率——周期弱加分）
             + 政策 2（负面清单——政府定价权风险——水电例外）

数据源：巨潮行业 PE（当前值）+ 新浪指数日线（涨幅/波动率）——全免费
ponytail: 行业 PE 十年分位待数据积累（巨潮可逐月快照——月频 120 次/行业——二期补）
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Any

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)
PROFILE_FILE = os.path.join(DATA_DIR, "industry_profile.json")

# 证监会行业代码 → 中证一级行业指数（新浪行情代码）
# A农林牧渔/B采矿/C制造/D电力热力燃气水/E建筑/F批发零售/G交通运输/
# H住宿餐饮/I信息/J金融/K房地产/L租赁商务/M科研/N水利环境/R文化体育/S综合
INDUSTRY_IDX: dict[str, str] = {
    "B": "sh000928",  # 采矿 → 中证能源
    "C": "sh000930",  # 制造 → 中证工业（近似——制造大类）
    "D": "sh000937",  # 电力热力燃气水 → 中证公用
    "G": "sh000930",  # 交通运输 → 中证工业（近似）
    "I": "sh000935",  # 信息 → 中证信息
    "J": "sh000934",  # 金融 → 中证金融
    "K": "sh000931",  # 房地产 → 中证可选（近似）
}

# 静态行业档案（书框架人工评级——格局 0-8：集中度/老大老二/周期强弱/变化大小）
# 政策负面：政府定价权风险（书：电力定价受管制——但水电例外——折旧>寿命）
DEFAULT_PROFILE: dict[str, dict[str, Any]] = {
    "金融": {
        "格局": 7,
        "政策负面": False,
        "备注": "寡头+牌照壁垒——受监管但盈利稳定（书：银行好行业）",
    },
    "公用": {
        "格局": 8,
        "政策负面": False,
        "备注": "自然垄断+刚需——水电例外（折旧>寿命——书明示）",
    },
    "能源": {
        "格局": 6,
        "政策负面": True,
        "备注": "周期强——煤炭油气价格受政策影响（煤价管控风险）",
    },
    "消费": {
        "格局": 7,
        "政策负面": False,
        "备注": "品牌壁垒+弱周期（书：消费是好行业）",
    },
    "医药": {"格局": 6, "政策负面": True, "备注": "集采政策风险（书：变化大封杀精神）"},
    "工业": {"格局": 5, "政策负面": False, "备注": "制造业分散——竞争激烈"},
    "信息": {
        "格局": 4,
        "政策负面": False,
        "备注": "变化大——书：变化大的行业封杀（回避——低分不否决）",
    },
    "可选": {"格局": 5, "政策负面": False, "备注": "汽车家电竞争激烈"},
}

# 证监会一级 → 档案键
CATEGORY_PROFILE: dict[str, str] = {
    "A": "消费",
    "B": "能源",
    "C": "工业",
    "D": "公用",
    "E": "工业",
    "F": "消费",
    "G": "工业",
    "H": "消费",
    "I": "信息",
    "J": "金融",
    "K": "可选",
    "L": "工业",
    "M": "工业",
    "N": "公用",
    "R": "消费",
    "S": "工业",
}

# 证监会一级 → 蛋卷指数估值代码（v1——2026-08-17：蛋卷百分位=现成历史位置）
# 蛋卷覆盖：银行/煤炭/白酒/医药/消费/信息/地产/证券等——缺公用/能源（fallback 巨潮）
DANJUAN_IDX: dict[str, str] = {
    "A": "SH000932",  # 农林牧渔→主要消费
    "B": "SZ399998",  # 采矿→中证煤炭（能源近似）
    "I": "SH000993",  # 信息→全指信息
    "J": "SZ399986",  # 金融→中证银行（默认——细分优先见 DANJUAN_IDX_SUB）
    "K": "SH000989",  # 房地产→全指可选
}

# F6 修复（2026-08-17 审核）：二级行业细分映射——证券/煤炭等有专属指数不用银行近似
DANJUAN_IDX_SUB: dict[str, str] = {
    "证券": "SZ399975",  # 资本市场服务（证券）→证券公司指数（蛋卷有）
    "资本市场服务": "SZ399975",
}

_eva_cache: dict[str, dict[str, float]] | None = None


def _danjuan_eva() -> dict[str, dict[str, float]]:
    """蛋卷指数估值（雪球系公开 API——63 指数 PE/PB/百分位）——模块级缓存

    返回 {指数代码: {pe_percentile, pe}}——失败 {}（fallback 巨潮横向）
    """
    global _eva_cache
    if _eva_cache:
        return _eva_cache
    try:
        import requests

        r = requests.get(
            "https://danjuanfunds.com/djapi/index_eva/dj",
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code != 200:
            return {}
        items = r.json().get("data", {}).get("items", [])
        out: dict[str, dict[str, float]] = {}
        for i in items:
            code = str(i.get("index_code", ""))
            pp = i.get("pe_percentile")
            pe = i.get("pe")
            if code and pp is not None:
                out[code] = {
                    "pe_percentile": float(pp),
                    "pe": float(pe) if pe is not None else 0.0,
                }
        _eva_cache = out
        return out
    except Exception:
        return {}


def _load_profile() -> dict[str, dict[str, Any]]:
    if os.path.exists(PROFILE_FILE):
        try:
            d = json.load(open(PROFILE_FILE, encoding="utf-8"))
            if d:
                return d
        except (OSError, ValueError):
            pass
    return DEFAULT_PROFILE


def _bs_code(code: str) -> str:
    """6 位 → baostock 9 位（600023→sh.600023 / 000001→sz.000001）"""
    c = code.split(".")[-1]
    if c.startswith("6") or c.startswith("9"):
        return f"sh.{c}"
    return f"sz.{c}"


def industry_of(code: str) -> dict[str, Any] | None:
    """个股 → 行业信息（baostock 证监会分类——失败返回 None——不阻塞打分）"""
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            return None
        rs = bs.query_stock_industry(code=_bs_code(code))
        out = None
        while rs.error_code == "0" and rs.next():
            r = rs.get_row_data()
            if len(r) > 4 and r[4] == "证监会行业分类":
                out = {"category": r[3][:1], "industry": r[3]}
                break
        bs.logout()
        return out
    except Exception:
        return None


def industry_pe_current(category: str) -> float | None:
    """行业当前 PE（巨潮——加权平均静态市盈率）——失败 None

    巨潮数据滞后（周末/节假日空）——date 自动回退最多 5 天
    """
    try:
        import akshare as ak

        for back in range(6):
            d = time.strftime("%Y%m%d", time.localtime(time.time() - back * 86400))
            try:
                df = ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类", date=d)
            except Exception:
                continue  # 该日无数据/接口异常——回退
            if df is None or df.empty:
                continue
            try:
                row = df[(df["行业层级"] == 1.0) & (df["行业编码"] == category)]
            except Exception:
                continue
            if row.empty:
                return None  # 数据有了但无此行业——不再回退（分类口径差异）
            pe = row.iloc[0]["静态市盈率-加权平均"]
            try:
                return float(pe)
            except (TypeError, ValueError):
                return None
        return None
    except Exception:
        return None


def industry_perf(idx_code: str) -> dict[str, float | None] | None:
    """行业指数表现（新浪日线）——2 年涨幅 + 3 年波动率——失败 None"""
    try:
        import akshare as ak

        df = ak.stock_zh_index_daily(symbol=idx_code)
        if len(df) < 100:
            return None
        closes = df["close"].tolist()
        cur = closes[-1]
        ret2y = (cur / closes[-250] - 1) * 100 if len(closes) >= 250 else None
        # 3 年波动率（750 日收益标准差年化）
        if len(closes) >= 750:
            w = closes[-750:]
            rets = [w[i] / w[i - 1] - 1 for i in range(1, len(w))]
            std = (
                sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / len(rets)
            ) ** 0.5
            vol3y = std * math.sqrt(250) * 100
        else:
            vol3y = None
        return {"ret_2y": ret2y, "vol_3y": vol3y}
    except Exception:
        return None


SNAPSHOT_FILE = os.path.join(DATA_DIR, "industry_pe_snapshots.jsonl")


def snapshot_monthly() -> bool:
    """行业 PE 逐月快照（2026-08-17：十年分位数据地基——每月首日记录）

    巨潮行业 PE 按日可拉——逐月积累（幂等——同月只记一次）
    一年后 12 点/五年 60 点——行业面'位置'纵向分位的数据来源
    """
    import json as _json

    ym = time.strftime("%Y-%m")
    try:
        seen = set()
        if os.path.exists(SNAPSHOT_FILE):
            for line in open(SNAPSHOT_FILE, encoding="utf-8"):
                try:
                    seen.add(_json.loads(line)["ym"])
                except (ValueError, KeyError):
                    continue
        if ym in seen:
            return False  # 本月已记——幂等
        import akshare as ak

        for back in range(6):
            d = time.strftime("%Y%m%d", time.localtime(time.time() - back * 86400))
            try:
                df = ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类", date=d)
            except Exception:
                continue
            if df is None or df.empty:
                continue
            rec: dict[str, Any] = {"ym": ym, "date": d}
            for _, row in df[df["行业层级"] == 1.0].iterrows():
                try:
                    # pyright 对 pandas iterrows 的 Series 推断保守——hasattr 守卫（运行时无问题）
                    cat = row["行业编码"]
                    pev = row["静态市盈率-加权平均"]
                    if hasattr(cat, "item"):
                        cat = cat.item()
                    if hasattr(pev, "item"):
                        pev = pev.item()
                    rec[str(cat)] = float(pev)  # type: ignore[arg-type]  # pyright 对 pandas iterrows 保守推断（运行时为标量）
                except (TypeError, ValueError):
                    continue
            if len(rec) > 2:
                with open(SNAPSHOT_FILE, "a", encoding="utf-8") as f:
                    f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
                return True
        return False
    except Exception:
        return False


def score_industry(code: str) -> dict[str, Any]:
    """行业面 20 分——失败维度返回 None（调用方给中性分——不因数据失败惩罚）"""
    ind = industry_of(code)
    if not ind:
        return {"error": "行业映射失败", "parts": []}
    cat = ind["category"]
    prof = _load_profile()
    key = CATEGORY_PROFILE.get(cat)
    profile = prof.get(key, {}) if key else {}
    idx = INDUSTRY_IDX.get(cat)
    pe = industry_pe_current(cat) if cat else None
    perf = industry_perf(idx) if idx else None

    parts: list[tuple[float, str]] = []
    # 格局 8（静态档案——书框架评级）——档案值异常安全兜底
    try:
        s1 = float(profile.get("格局", 5)) if profile else 5.0
    except (TypeError, ValueError):
        s1 = 5.0
    parts.append((s1, f"格局{key or cat}：{profile.get('备注', '默认中性')}"))
    # 位置 6（蛋卷百分位优先——现成历史位置——fallback 巨潮横向 PE + 涨幅防接盘）
    s2 = 3.0  # 中性默认
    note = "位置未知（中性）"
    eva = _danjuan_eva()
    # F6（2026-08-17 审核）：二级行业细分优先（证券→证券公司指数——不用银行近似）
    dj_code = None
    if ind.get("industry"):
        for sub, idx_code in DANJUAN_IDX_SUB.items():
            if sub in ind["industry"]:
                dj_code = idx_code
                break
    if dj_code is None:
        dj_code = DANJUAN_IDX.get(cat)
    if dj_code and dj_code in eva:
        pp = eva[dj_code]["pe_percentile"]
        if pp < 0.3:
            s2 = 6.0
        elif pp < 0.6:
            s2 = 4.5
        elif pp < 0.8:
            s2 = 3.0
        else:
            s2 = 1.5  # 历史高位（书 L5524 百分位>80 减仓区）
        note = f"行业PE百分位 {pp * 100:.0f}%（蛋卷——历史位置）"
    elif pe is not None:
        # fallback：巨潮横向评分（蛋卷未覆盖行业——公用/能源）
        if pe < 12:
            s2 = 6.0
        elif pe < 20:
            s2 = 4.5
        elif pe < 30:
            s2 = 3.0
        else:
            s2 = 1.0
        note = f"行业PE {pe:.0f}（横向——蛋卷未覆盖）"
    if perf and perf["ret_2y"] is not None and perf["ret_2y"] > 50:
        s2 = max(0.0, s2 - 2.0)  # 2 年涨超 50%——防接盘（书 N10 精神）
        note += f" 2年涨{perf['ret_2y']:.0f}%（高位——扣防接盘分）"
    elif perf and perf["ret_2y"] is not None and perf["ret_2y"] < -20:
        s2 = min(6.0, s2 + 1.0)  # 深跌——位置好
        note += f" 2年跌{perf['ret_2y']:.0f}%（低位——加分）"
    parts.append((s2, note))
    # 周期 4（3 年波动率——周期弱加分）
    s3 = 2.0  # 中性
    if perf and perf["vol_3y"] is not None:
        v = perf["vol_3y"]
        if v < 20:
            s3 = 4.0
        elif v < 30:
            s3 = 3.0
        elif v < 45:
            s3 = 2.0
        else:
            s3 = 1.0
        parts.append((s3, f"3年波动率{v:.0f}%（周期{'弱' if v < 30 else '强'}）"))
    else:
        parts.append((s3, "3年波动率未知（中性）"))
    # 政策 2（负面清单——政府定价权）
    s4 = 2.0 if not profile.get("政策负面") else 0.0
    parts.append(
        (s4, f"政策面：{'无政府定价权风险' if s4 else '政府定价/政策负面（书：风险）'}")
    )
    total = round(sum(p[0] for p in parts), 1)
    return {"total": total, "parts": parts, "category": ind["industry"], "key": key}


if __name__ == "__main__":
    import sys

    for code in sys.argv[1:] or ["sh.600036", "sh.601601", "sh.600023"]:
        r = score_industry(code)
        if "error" in r:
            print(f"{code}: {r['error']}")
            continue
        print(f"{code} [{r['category']}→{r.get('key')}] 行业面 {r['total']}/20")
        for s, note in r["parts"]:
            print(f"   {s}  {note}")
