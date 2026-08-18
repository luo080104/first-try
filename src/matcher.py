# matcher.py - SKU 品类适配器原型 v0.1（阶段 1）
# 设计：每品类一套解析规则，输出结构化"匹配键"，跨平台按匹配键对齐
import re
from typing import Optional

from diag import diag

# ========== 品牌提取（通用）==========

# 常见品牌表（后续可扩充/人工维护）
BRAND_TABLE = [
    "波司登",
    "李宁",
    "坦博尔",
    "鸭鸭",
    "雪中飞",
    "骆驼",
    "优衣库",
    "耐克",
    "阿迪达斯",
    "安踏",
    "金典",
    "伊利",
    "蒙牛",
    "特仑苏",
    "纯甄",
    "认养一头牛",
    "蓝月亮",
    "立白",
    "超能",
    "奥妙",
    "威露士",
    "植护",
]


def extract_brand(title: str) -> str:
    """提取品牌：优先【】内，再查品牌表"""
    m = re.search(r"【([^】]+)】", title)
    if m and m.group(1) in BRAND_TABLE:
        return m.group(1)
    for b in BRAND_TABLE:
        if b in title:
            return b
    return ""


# ========== 食品适配器 ==========


class FoodMatcher:
    """匹配键：品牌 + 单瓶容量ml + 瓶数（例：金典|250|12）"""

    @staticmethod
    def parse(title: str) -> dict:
        brand = extract_brand(title)
        # 规格：250ml*12 / 200ml×10 / 250mlx16盒 / 12盒*250ml（反向）/ 250ml*12盒*2箱（倍增）
        m = re.search(
            r"(\d+)\s*ml\s*[×xX*＊]\s*(\d+)(?:\s*(?:盒|瓶|包|提)\s*[×xX*＊]\s*(\d+)\s*(?:箱|提|件))?",
            title,
            re.I,
        )
        spec = None
        if m:
            count = int(m.group(2)) * (int(m.group(3)) if m.group(3) else 1)
            spec = {"ml": int(m.group(1)), "count": count}
        else:
            # 反向：12盒*250ml / 12瓶×200ml
            m2 = re.search(
                r"(\d+)\s*(?:盒|瓶|包|提)\s*[×xX*＊]\s*(\d+)\s*ml", title, re.I
            )
            if m2:
                spec = {"ml": int(m2.group(2)), "count": int(m2.group(1))}
            else:
                # 兜底：只提容量
                m3 = re.search(r"(\d+)\s*ml", title)
                if m3:
                    spec = {"ml": int(m3.group(1)), "count": None}
        return {"brand": brand, "spec": spec}

    @staticmethod
    def key(item: dict) -> str:
        """生成匹配键"""
        p = item.get("parsed", {})
        spec = p.get("spec") or {}
        return f"{p.get('brand', '')}|{spec.get('ml', '')}|{spec.get('count', '')}"


# ========== 服饰适配器 ==========


class ClothingMatcher:
    """匹配键：品牌 + 长度/性别/系列款号特征词（标题无显式款号时弱匹配）"""

    FEATURES = (
        "短款",
        "长款",
        "中长款",
        "连帽",
        "收腰",
        "男",
        "女",
        "鹅绒",
        "白鸭绒",
        "鸭绒",
        "面包服",
        "白月光",
        "极寒",
        "星空",
        "奥莱",
        "反季",
    )

    @staticmethod
    def parse(title: str) -> dict:
        brand = extract_brand(title)
        feats = [f for f in ClothingMatcher.FEATURES if f in title]
        return {"brand": brand, "features": feats}

    @staticmethod
    def key(item: dict) -> str:
        p = item.get("parsed", {})
        return f"{p.get('brand', '')}|{'/'.join(p.get('features', []))}"


# ========== 数码家电适配器 ==========


def classify_digital(title: str) -> str:
    """数码商品类型归类（规则识别，顺序敏感：笔记本>显卡>整机>配件）"""
    t = (title or "").lower()
    # 文具排除：纸质/手账/线圈本不是电脑笔记本
    if any(
        k in t
        for k in (
            "纸质",
            "手账",
            "手帐",
            "文具",
            "线圈",
            "记事本",
            "办公用",
            "商务",
            "横线",
            "牛皮纸",
            "a5",
            "a4",
            "b5",
            "草稿本",
            "便签",
        )
    ):
        return "其他"
    if any(
        k in t
        for k in (
            "游戏本",
            "笔记本",
            "笔记本电脑",
            "本本",
            "thinkpad",
            "灵越",
            "拯救者",
            "天选",
            "暗影精灵",
            "星book",
            "yoga",
        )
    ):
        return "笔记本"
    # 配件优先于显卡：显卡支架/散热硅脂都是配件（用户不会当显卡买）
    if any(
        k in t
        for k in (
            "支架",
            "硅脂",
            "贴纸",
            "散热器",
            "散热片",
            "风扇",
            "螺丝",
            "电源线",
            "膜",
            "盒子",
            "线材",
            "转接",
            "挡板",
            "背板",
        )
    ):
        return "配件"
    if any(k in t for k in ("独立显卡", "显卡", " gpu", "rtx", "gtx")):
        return "显卡"
    if any(k in t for k in ("主机", "台式", "整机", "itx", "atx", "机箱")):
        return "整机"
    return "其他"


class DigitalMatcher:
    """数码家电：品牌 + 型号 + 核心配置（GPU/CPU/内存/存储）"""

    BRANDS = (
        "联想",
        "惠普",
        "戴尔",
        "华硕",
        "宏碁",
        "微星",
        "机械革命",
        "神舟",
        "苹果",
        "华为",
        "小米",
        "荣耀",
        "三星",
        "索尼",
        "松下",
        "格力",
        "美的",
        "海尔",
        "TCL",
        "海信",
    )

    CONFIG_PATTERNS = (
        (r"rtx\s*\d+", "gpu"),  # RTX5080/RTX 5080
        (r"gtx\s*\d+", "gpu"),
        (r"酷睿\s*\S*", "cpu"),  # 酷睿Ultra9
        (r"i[3579]-?\d+\w*", "cpu"),  # i7-14700HX
        (r"锐龙\s*\S*", "cpu"),  # 锐龙7
        (r"(\d+)g[bd]", "ram"),  # 32G/16GB
        (r"(\d+)t[bd]", "storage"),  # 1T/1TB
        (r"(\d+)g[bd]\s*ssd", "storage"),
    )

    @staticmethod
    def parse(title: str) -> dict:
        brand = ""
        for b in DigitalMatcher.BRANDS:
            if b in title:
                brand = b
                break
        # 系列型号：系列词表匹配（耀世16Ultra / 暗影精灵Max16 / 战66）
        _re = re
        SERIES_WORDS = [
            "耀世",
            "暗影精灵",
            "光影精灵",
            "拯救者",
            "天选",
            "灵越",
            "星Book",
            "星book",
            "战66",
            "战99",
            "小新",
            "ThinkPad",
            "thinkpad",
            "Yoga",
            "yoga",
            "OMEN",
            "omen",
            "暗影",
            "蛟龙",
            "极光",
        ]
        series = ""
        for w in SERIES_WORDS:
            m = _re.search(w + r" ?[A-Za-z0-9]{0,12}", title, _re.I)
            if m:
                series = m.group(0)
                # 截断：遇到 GPU/CPU 关键词就停（避免吞掉配置数字）
                cut = _re.search(
                    r"(?i)(rtx\s*\d|gtx\s*\d|酷睿|锐龙|i[3579]-?\d|u\s*\d|amd|intel)",
                    series,
                )
                if cut:
                    series = series[: cut.start()]
                # 清理尾部连续 3-4 位数字组（GPU 列表：5060 5070ti 5080）与孤立 CPU 代号（U9/i7）
                series = _re.sub(r"(?i)(\s+\d{3,4}[a-z]?)+$", "", series.strip())
                series = _re.sub(r"(?i)\s+[a-z]\d+$", "", series.strip())
                break
        # 兜底：品牌后 2-6 字
        if not series:
            m2 = _re.search(r"[一-龥]{2,6}\d{0,3}[A-Za-z]{0,6}", title)
            series = m2.group(0) if m2 else ""

        config = {}
        low = title.lower()
        for pat, key in DigitalMatcher.CONFIG_PATTERNS:
            m2 = _re.search(pat, low)
            if m2:
                config[key] = m2.group(0)
        # 纯数字 GPU 兜底（WorkBuddy 建议）："耀世16 Ultra 5080" → gpu=5080
        # 排除内存/硬盘数字（32G/1T 已匹配 ram/storage），只认 4 位 GPU 型号
        if "gpu" not in config:
            m3 = _re.search(
                r"(?:^|[^\d])(50[5-9]0|50[5-9]0\s*ti)(?=$|[^\d])", title, _re.I
            )
            if m3:
                config["gpu"] = m3.group(1).replace(" ", "").lower()
        return {"brand": brand, "series": series, "config": config}

    @staticmethod
    def key(item: dict) -> str:
        p = item.get("parsed", {})
        # 同品牌+同系列归一化即同组（配置差异用标题展示，跨平台对比优先）
        brand = p.get("brand", "")
        series = DigitalMatcher._norm(p.get("series", ""))
        return f"{brand}|{series}"

    @staticmethod
    def _norm(s: str) -> str:
        """系列名归一化：去空格、小写（耀世16Ultra == 耀世16 Ultra）"""
        return s.replace(" ", "").replace("-", "").lower()[:25]


# ========== 适配器注册 ==========

ADAPTERS = {
    "服饰": ClothingMatcher,
    "食品": FoodMatcher,
    "日用百货": FoodMatcher,  # 日用规格化商品暂用食品规则（品牌+规格）
    "数码家电": DigitalMatcher,
}

# ========== v5.2 P2：店铺类型 + 正品保障 + 单斤价（比价购物助手/购物研究助手案例）==========


def shop_type_of(item: dict) -> str:
    """店铺类型标注：自营/天猫/旗舰店/百亿补贴/官方（空=普通店铺）"""
    plat = item.get("platform", "")
    title = str(item.get("title") or "")
    shop = str(item.get("shopName") or "")
    if plat == "jd":
        if "自营" in title or "自营" in shop:
            return "自营"
        return ""
    if plat == "tb":
        if item.get("is_tmall"):
            return "天猫"
        if "旗舰店" in shop:
            return "旗舰店"
        return ""
    if plat == "pdd":
        if "百亿补贴" in title or "百亿补贴" in shop:
            return "百亿补贴"
        return ""
    if plat == "vip":
        return item.get("shop_type") or ("自营" if "自营" in shop else "")
    return ""


def genuine_pick(items: list) -> Optional[dict]:
    """正品保障推荐：组内优先 京东自营 > 天猫/旗舰店 > 唯品自营；无则 None"""
    if not items:
        return None
    order = {"京东自营": 0, "天猫": 1, "旗舰店": 1, "唯品自营": 2}
    best_it, best_rank = None, 99
    for it in items:
        st = shop_type_of(it)
        if not st:
            continue
        key = (it.get("platform") or "") + st
        rank = order.get(key, 5)
        if rank < best_rank:
            best_rank, best_it = rank, it
    return best_it


def unit_price_of(item: dict, category: str = "") -> Optional[float]:
    """食品单斤价：每百毫升价格（元）。非食品/无规格返回 None"""
    if category != "食品":
        return None
    p = FoodMatcher.parse(str(item.get("title") or ""))
    spec = p.get("spec") or {}
    ml, count = spec.get("ml"), spec.get("count")
    price = item.get("actualPrice") or 0
    if ml and count and price:
        return round(price / (ml * count) * 100, 2)  # 每 100ml
    if ml and price:
        return round(price / ml * 100, 2)
    return None


def annotate_item(it: dict, category: str):
    """给单条商品补店铺类型 + 单价 + 店铺信誉分（就地修改）"""
    it["shop_type"] = shop_type_of(it)
    up = unit_price_of(it, category)
    if up:
        it["unit_price"] = up
    try:
        from shop_rating import shop_rating_of

        sr = shop_rating_of(it)
        it["shop_rating"] = sr["rating"]
        it["shop_signals"] = sr["label"]
    except Exception as e:
        diag("matcher", "annotate_item", e, "店铺评分失败——该条目缺评分字段")
    return it


def annotate_group(g: dict, category: str):
    """给分组补正品保障推荐（就地修改）"""
    plats = g.get("platforms")
    items = list(plats.values()) if isinstance(plats, dict) else (plats or [])
    for it in items:
        annotate_item(it, category)
    gen = genuine_pick(items)
    if gen:
        g["genuine"] = {
            "platform": gen.get("platform"),
            "price": gen.get("actualPrice"),
            "title": (gen.get("title") or "")[:30],
            "shop_type": gen.get("shop_type"),
        }
    return g


def parse_items(items: list, category: str) -> list:
    """给搜索结果批量打解析标签"""
    adapter = ADAPTERS.get(category)
    if adapter is None:
        return items
    for it in items:
        it["parsed"] = adapter.parse(it.get("title", ""))
    return items


def group_by_sku(items: list, category: str) -> dict:
    """按匹配键分组，返回 {匹配键: [商品...]}"""
    adapter = ADAPTERS.get(category)
    if adapter is None:
        return {"未解析": items}
    groups = {}
    for it in items:
        k = adapter.key(it)
        groups.setdefault(k, []).append(it)
    return groups


if __name__ == "__main__":
    # 自测
    tests = [
        ("食品", "金典高钙低脂纯牛奶/纯牛奶250ml*12盒"),
        ("食品", "伊利金典纯牛奶250ml*12盒 如木新包装 礼盒装"),
        ("食品", "【5月】金典纯牛奶250ml*16盒带提手"),
        ("服饰", "【爆款】波司登男士冬季短款羽绒服"),
        ("服饰", "波司登2026新款女士短款连帽90白鸭绒面包服"),
    ]
    for cat, title in tests:
        adapter = ADAPTERS[cat]
        parsed = adapter.parse(title)
        print(f"[{cat}] {title[:30]} → {parsed}")
