# -*- coding: utf-8 -*-
"""规范 3 执行：27 处静默 except → 显式 diag 记录（2026-08-18，v2 内容匹配版）
不依赖行号：按「except Exception: + pass」模式定位，与映射队列按文件顺序配对。
"""
import py_compile
import re
import sys

ROOT = "C:/Users/luoji/shopping-agent"

# (文件, component, fn, hint) —— 同一文件内按出现顺序配对
MAP = [
    ("src/llm_parse.py", "llm_parse", "_log_trace", "日志文件写入失败——丢一条 trace 不影响主流程"),
    ("src/llm_parse.py", "llm_parse", "parse_intent", "LLM 偏好提取失败——跳过该次偏好学习"),
    ("src/llm_parse.py", "llm_parse", "parse_intent", "usage 记账失败——成本记录缺失"),
    ("src/llm_parse.py", "llm_parse", "generate_options", "usage 记账失败——成本记录缺失"),
    ("src/db.py", "db", "get_advice_cache", "读建议缓存异常——降级直查（宁可慢不可错）"),
    ("src/db.py", "db", "set_user_pref", "幂等迁移 source 列失败（列已存在属预期）——建议改 PRAGMA 检查，本轮不改逻辑"),
    ("src/db.py", "db", "set_user_pref", "幂等迁移 confidence 列失败（列已存在属预期）——建议改 PRAGMA 检查，本轮不改逻辑"),
    ("src/browser_pool.py", "browser_pool", "_hide_browser", "DrissionPage hide 失败——继续尝试 ctypes 兜底"),
    ("src/browser_pool.py", "browser_pool", "_hide_browser", "ctypes 强制隐藏失败——窗口可能可见"),
    ("src/browser_pool.py", "browser_pool", "get_browser", "退出旧浏览器实例失败——强制 pop 重建"),
    ("src/browser_pool.py", "browser_pool", "_sweep_hide", "定时隐藏失败——下次 sweep 再试"),
    ("src/browser_pool.py", "browser_pool", "rehide", "隐藏失败——下次再试"),
    ("src/routes/search.py", "routes.search", "search_bili_api", "CDP 探测失败——降级走 Edge 可执行文件路径"),
    ("src/routes/search.py", "routes.search", "step", "搜索日志写入失败——不影响搜索本身"),
    ("src/routes/search.py", "routes.search", "gen", "历史价汇总失败——跳过图表只出文本"),
    ("src/routes/search.py", "routes.search", "gen", "连接关闭失败——finally 兜底泄漏风险"),
    ("src/detail_crawler.py", "detail_crawler", "first", "店铺信息解析失败——该条目缺店铺字段"),
    ("src/detail_crawler.py", "detail_crawler", "crawl_tb_detail", "tb 隐藏失败——窗口可能可见"),
    ("src/detail_crawler.py", "detail_crawler", "crawl_jd_detail", "jd 隐藏失败——窗口可能可见"),
    ("src/tb_search.py", "tb_search", "search_taobao", "tb 隐藏失败——窗口可能可见"),
    ("src/tb_search.py", "tb_search", "_search_via_listen", "商品链接提取失败——该条无链接"),
    ("src/vip_search.py", "vip_search", "search_vip", "标题提取失败——跳过该条目字段"),
    ("src/vip_search.py", "vip_search", "search_vip", "价格解析失败——该条价格缺失"),
    ("src/vip_search.py", "vip_search", "search_vip", "品牌提取失败——该条无品牌"),
    ("src/vip_search.py", "vip_search", "search_vip", "vip 隐藏失败——窗口可能可见"),
    ("src/pdd_search.py", "pdd_search", "search_pdd", "pdd 隐藏失败——窗口可能可见"),
    ("src/jd_search.py", "jd_search", "search_jd", "sku 提取失败——尝试正则兜底"),
    ("src/jd_search.py", "jd_search", "search_jd", "sku 正则兜底失败——该条无 sku"),
    ("src/jd_search.py", "jd_search", "search_jd", "jd 隐藏失败——窗口可能可见"),
    ("src/guide.py", "guide", "_gc_sessions", "旧会话清理失败——下次启动再清"),
    ("src/guide.py", "guide", "_call_llm", "usage 记账失败——成本记录缺失"),
    ("src/guide.py", "guide", "search_recommend", "实时搜索失败——items 为空继续走库"),
    ("src/guide.py", "guide", "search_recommend", "历史库查询失败——该轮无历史数据"),
    ("src/matcher.py", "matcher", "annotate_item", "店铺评分失败——该条目缺评分字段"),
    ("src/score.py", "score", "interact_score", "评论数解析失败——返回默认 0.3"),
    ("src/wander.py", "wander", "pick", "关联召回失败——跳过该路召回"),
    ("src/compare.py", "compare", "_call_llm_retry", "usage 记账失败——成本记录缺失"),
    ("src/app.py", "app", "app_startup", "stdout 重定向失败——日志通道缺失"),
    ("src/app.py", "app", "app_startup", "stderr 重定向失败——日志通道缺失"),
    ("src/app.py", "app", "app_startup", "UTF-8 reconfigure 失败——emoji print 可能崩"),
    ("src/routes/api.py", "routes.api", "api_advice", "建议缓存写入失败——本次不缓存"),
    ("src/fill_shop_founded.py", "fill_shop_founded", "crawl_shop_founded", "窗口隐藏失败——可能弹窗"),
    ("src/llm_usage.py", "llm_usage", "record_usage", "usage 写库失败——成本记录丢失"),
]

EXC = re.compile(r"^(\s*)except Exception:\s*$")
PASS = re.compile(r"^(\s*)pass\s*$")


def process(fname: str, entries: list) -> int:
    path = f"{ROOT}/{fname}"
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"  !! {fname} 读取失败: {e}")
        return 0
    # 找所有 except+pass 对
    spots = []
    i = 0
    while i < len(lines) - 1:
        m = EXC.match(lines[i])
        if m and PASS.match(lines[i + 1]):
            spots.append(i)
            i += 2
        else:
            i += 1
    if len(spots) < len(entries):
        print(f"  !! {fname}: 找到 {len(spots)} 处 except+pass，期望 {len(entries)}——跳过")
        return 0
    for idx, (_, comp, fn, hint) in enumerate(entries):
        ln = spots[idx]
        m = EXC.match(lines[ln])
        if m is None:
            print(f"  !! {fname}:{ln + 1} 行已被修改过——跳过")
            continue
        indent = m.group(1)
        lines[ln] = f"{indent}except Exception as e:\n"
        lines[ln + 1] = f'{indent}    diag("{comp}", "{fn}", e, "{hint}")\n'
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
    except OSError as e:
        print(f"  !! {fname} 写入失败: {e}")
        return 0
    return len(entries)


def ensure_import(fname: str) -> bool:
    path = f"{ROOT}/{fname}"
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"  !! {fname} 读取失败: {e}")
        return False
    if "from diag import diag" in text:
        return True
    lines = text.splitlines(keepends=True)
    idx = None
    for i, l in enumerate(lines):
        if re.match(r"^(import |from )", l):
            idx = i
            break
    if idx is None:
        idx = len(lines)
    lines.insert(idx, "from diag import diag\n")
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
    except OSError as e:
        print(f"  !! {fname} 写入失败: {e}")
        return False
    return True


def main() -> int:
    by_file: dict = {}
    for fname, comp, fn, hint in MAP:
        by_file.setdefault(fname, []).append((fname, comp, fn, hint))
    total = 0
    for fname, entries in by_file.items():
        n = process(fname, entries)
        print(f"{fname}: {n}/{len(entries)}")
        total += n
    print(f"总计: {total}/{len(MAP)}")
    for f in by_file:
        ensure_import(f)
    print(f"import 注入: {len(by_file)} 文件")
    bad = 0
    for f in by_file:
        try:
            py_compile.compile(f"{ROOT}/{f}", doraise=True)
        except py_compile.PyCompileError as e:
            print(f"  !! 编译失败 {f}: {e}")
            bad += 1
    print(f"编译: {'全部通过' if not bad else f'{bad} 失败'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
