# llm_usage.py - AI 费用统计（Agent Part 会话追踪借鉴）
# 各 LLM 调用点记录 token → 估算费用（元）→ 页面可查本月花费
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')

# DeepSeek 单价（元/百万 token，近似值；V4-Flash 便宜 / V4-Pro 贵）
PRICING = {
    'deepseek-v4-flash': {'input': 0.5, 'output': 2.0},
    'deepseek-v4-pro': {'input': 2.0, 'output': 8.0},
}
DEFAULT = {'input': 1.0, 'output': 3.0}


def record_usage(model: str, input_tokens: int, output_tokens: int, scene: str = '',
                 cache_hit: int = 0, cache_miss: int = 0):
    """记录一次 LLM 调用费用（幂等写库，失败不影响主流程）
    2026-08-11 Reasonix 启发：记录缓存命中/未命中 token（DeepSeek 缓存价差 50-120 倍）"""
    try:
        p = PRICING.get(model, DEFAULT)
        # 缓存命中按 1/50 计（V4-Flash 0.02 vs 1；V4-Pro 0.025 vs 3——近似取输入价的 2%）
        hit = int(cache_hit or 0)
        miss = int(cache_miss or 0)
        eff_input = miss + hit * 0.02
        cost = (eff_input / 1e6) * p['input'] + (int(output_tokens or 0) / 1e6) * p['output']
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''INSERT INTO ai_usage (model, input_tokens, output_tokens, cost, scene, cache_hit, cache_miss)
            VALUES (?,?,?,?,?,?,?)''',
                     (model, int(input_tokens or 0), int(output_tokens or 0), round(cost, 5), scene or '',
                      hit, miss))
        conn.commit()
        conn.close()
    except Exception:
        pass


def month_cost() -> dict:
    """本月费用统计"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COALESCE(SUM(cost),0) c FROM ai_usage WHERE created_at >= date('now','localtime','start of month')").fetchone()['c']
        calls = conn.execute("SELECT COUNT(*) n FROM ai_usage WHERE created_at >= date('now','localtime','start of month')").fetchone()['n']
        by_scene = conn.execute("SELECT scene, COUNT(*) n, COALESCE(SUM(cost),0) c FROM ai_usage GROUP BY scene ORDER BY c DESC").fetchall()
        conn.close()
        return {'month_cost': round(total, 4), 'calls': calls,
                'by_scene': [{'scene': r['scene'] or '其他', 'n': r['n'], 'cost': round(r['c'], 4)} for r in by_scene]}
    except Exception:
        return {'month_cost': 0, 'calls': 0, 'by_scene': []}
