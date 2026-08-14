"""可转债高级策略引擎（观复 tools/cb_strategy）

来源：
- cb-strategy-mcp (github.com/Lozzi1910/cb-strategy-mcp, MIT) — 6基础策略
- convertible-bond-crawler (github.com/zhezhang-pojo/convertible-bond-crawler, MIT) — 8扩展策略思路

数据源（双源）：
- 东方财富 (AKShare bond_zh_cov) — 全量1049条，免费无需cookie，2分钟缓存
- 集思录 (AKShare bond_cb_jsl) — 策略字段全(正股PB/回售触发价/到期收益/剩余年限等)
  - 无cookie: 30条样例（次新债/四象限可跑，其他策略需cookie全量）
  - 有cookie: 全量~500条（所有策略可用）

策略总览（6基础+7扩展=13策略）：
基础6：双低/三低/YTM排名/强赎监控/下修博弈/市场总览（东方财富源）
扩展7：到期保本/回售摸彩/低价格低溢价(增强)/三低(增强)/下修博弈/次新债/四象限分类（集思录源）

观复采用：
- MVP：东方财富6基础策略（免费跑通）
- 二期：集思录cookie+7扩展策略（策略更全）
- 二期可选：cb-strategy-mcp 当 MCP Server，观复直接调工具

字段映射（宁稳网 → 集思录）见 strategies_ext.py 文件头注释
"""

from .strategies import (
    dual_low_strategy,
    triple_low_strategy,
    ytm_ranking,
    early_redemption_monitor,
    revision_arbitrage_analysis,
    market_overview,
)
from .data import get_bond_comparison, get_bond_spot, get_bond_history
from .strategies_ext import (
    filter_profit_due,
    filter_return_lucky,
    filter_double_low_enhanced,
    filter_three_low_enhanced,
    filter_downward_revise,
    filter_new_bond,
    classify_quadrants,
    get_jsl_data,
)

__all__ = [
    # 基础6（东方财富源）
    "dual_low_strategy", "triple_low_strategy", "ytm_ranking",
    "early_redemption_monitor", "revision_arbitrage_analysis", "market_overview",
    # 扩展7（集思录源，cookie可选）
    "filter_profit_due", "filter_return_lucky", "filter_double_low_enhanced",
    "filter_three_low_enhanced", "filter_downward_revise", "filter_new_bond",
    "classify_quadrants",
    # 数据层
    "get_bond_comparison", "get_bond_spot", "get_bond_history", "get_jsl_data",
]
