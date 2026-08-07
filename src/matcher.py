# matcher.py - SKU 品类适配器原型 v0.1（阶段 1）
# 设计：每品类一套解析规则，输出结构化"匹配键"，跨平台按匹配键对齐
import re

# ========== 品牌提取（通用）==========

# 常见品牌表（后续可扩充/人工维护）
BRAND_TABLE = [
    '波司登', '李宁', '坦博尔', '鸭鸭', '雪中飞', '骆驼', '优衣库', '耐克', '阿迪达斯', '安踏',
    '金典', '伊利', '蒙牛', '特仑苏', '纯甄', '认养一头牛',
    '蓝月亮', '立白', '超能', '奥妙', '威露士', '植护',
]

def extract_brand(title: str) -> str:
    """提取品牌：优先【】内，再查品牌表"""
    m = re.search(r'【([^】]+)】', title)
    if m and m.group(1) in BRAND_TABLE:
        return m.group(1)
    for b in BRAND_TABLE:
        if b in title:
            return b
    return ''

# ========== 食品适配器 ==========

class FoodMatcher:
    """匹配键：品牌 + 单瓶容量ml + 瓶数（例：金典|250|12）"""

    @staticmethod
    def parse(title: str) -> dict:
        brand = extract_brand(title)
        # 规格：250ml*12 / 200ml×10 / 250mlx16盒
        m = re.search(r'(\d+)\s*ml\s*[×x*＊]\s*(\d+)', title)
        spec = None
        if m:
            spec = {'ml': int(m.group(1)), 'count': int(m.group(2))}
        else:
            # 兜底：只提容量
            m2 = re.search(r'(\d+)\s*ml', title)
            if m2:
                spec = {'ml': int(m2.group(1)), 'count': None}
        return {'brand': brand, 'spec': spec}

    @staticmethod
    def key(item: dict) -> str:
        """生成匹配键"""
        p = item.get('parsed', {})
        spec = p.get('spec') or {}
        return f"{p.get('brand','')}|{spec.get('ml','')}|{spec.get('count','')}"

# ========== 服饰适配器 ==========

class ClothingMatcher:
    """匹配键：品牌 + 长度/性别/填充特征词（标题无显式款号，弱匹配）"""

    FEATURES = ['短款', '长款', '中长款', '连帽', '收腰', '男', '女', '鹅绒', '白鸭绒', '鸭绒', '面包服']

    @staticmethod
    def parse(title: str) -> dict:
        brand = extract_brand(title)
        feats = [f for f in ClothingMatcher.FEATURES if f in title]
        return {'brand': brand, 'features': feats}

    @staticmethod
    def key(item: dict) -> str:
        p = item.get('parsed', {})
        return f"{p.get('brand','')}|{'/'.join(p.get('features', []))}"

# ========== 适配器注册 ==========

ADAPTERS = {
    '服饰': ClothingMatcher,
    '食品': FoodMatcher,
    '日用百货': FoodMatcher,  # 日用规格化商品暂用食品规则（品牌+规格）
    '数码家电': None,          # 阶段 2 再做
}

def parse_items(items: list, category: str) -> list:
    """给搜索结果批量打解析标签"""
    adapter = ADAPTERS.get(category)
    if adapter is None:
        return items
    for it in items:
        it['parsed'] = adapter.parse(it.get('title', ''))
    return items

def group_by_sku(items: list, category: str) -> dict:
    """按匹配键分组，返回 {匹配键: [商品...]}"""
    adapter = ADAPTERS.get(category)
    if adapter is None:
        return {'未解析': items}
    groups = {}
    for it in items:
        k = adapter.key(it)
        groups.setdefault(k, []).append(it)
    return groups

if __name__ == '__main__':
    # 自测
    tests = [
        ('食品', '金典高钙低脂纯牛奶/纯牛奶250ml*12盒'),
        ('食品', '伊利金典纯牛奶250ml*12盒 如木新包装 礼盒装'),
        ('食品', '【5月】金典纯牛奶250ml*16盒带提手'),
        ('服饰', '【爆款】波司登男士冬季短款羽绒服'),
        ('服饰', '波司登2026新款女士短款连帽90白鸭绒面包服'),
    ]
    for cat, title in tests:
        adapter = ADAPTERS[cat]
        parsed = adapter.parse(title)
        print(f'[{cat}] {title[:30]} → {parsed}')
