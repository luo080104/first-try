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
        # 规格：250ml*12 / 200ml×10 / 250mlx16盒 / 12盒*250ml（反向）/ 250ml*12盒*2箱（倍增）
        m = re.search(r'(\d+)\s*ml\s*[×xX*＊]\s*(\d+)(?:\s*(?:盒|瓶|包|提)\s*[×xX*＊]\s*(\d+)\s*(?:箱|提|件))?', title, re.I)
        spec = None
        if m:
            count = int(m.group(2)) * (int(m.group(3)) if m.group(3) else 1)
            spec = {'ml': int(m.group(1)), 'count': count}
        else:
            # 反向：12盒*250ml / 12瓶×200ml
            m2 = re.search(r'(\d+)\s*(?:盒|瓶|包|提)\s*[×xX*＊]\s*(\d+)\s*ml', title, re.I)
            if m2:
                spec = {'ml': int(m2.group(2)), 'count': int(m2.group(1))}
            else:
                # 兜底：只提容量
                m3 = re.search(r'(\d+)\s*ml', title)
                if m3:
                    spec = {'ml': int(m3.group(1)), 'count': None}
        return {'brand': brand, 'spec': spec}

    @staticmethod
    def key(item: dict) -> str:
        """生成匹配键"""
        p = item.get('parsed', {})
        spec = p.get('spec') or {}
        return f"{p.get('brand','')}|{spec.get('ml','')}|{spec.get('count','')}"

# ========== 服饰适配器 ==========

class ClothingMatcher:
    """匹配键：品牌 + 长度/性别/系列款号特征词（标题无显式款号时弱匹配）"""

    FEATURES = ['短款', '长款', '中长款', '连帽', '收腰', '男', '女', '鹅绒', '白鸭绒', '鸭绒', '面包服',
                '白月光', '极寒', '星空', '奥莱', '反季']

    @staticmethod
    def parse(title: str) -> dict:
        brand = extract_brand(title)
        feats = [f for f in ClothingMatcher.FEATURES if f in title]
        return {'brand': brand, 'features': feats}

    @staticmethod
    def key(item: dict) -> str:
        p = item.get('parsed', {})
        return f"{p.get('brand','')}|{'/'.join(p.get('features', []))}"

# ========== 数码家电适配器 ==========

class DigitalMatcher:
    """数码家电：品牌 + 型号 + 核心配置（GPU/CPU/内存/存储）"""

    BRANDS = ['联想', '惠普', '戴尔', '华硕', '宏碁', '微星', '机械革命', '神舟', '苹果',
              '华为', '小米', '荣耀', '三星', '索尼', '松下', '格力', '美的', '海尔', 'TCL', '海信']

    CONFIG_PATTERNS = [
        (r'rtx\s*\d+', 'gpu'),          # RTX5080/RTX 5080
        (r'gtx\s*\d+', 'gpu'),
        (r'酷睿\s*\S*', 'cpu'),          # 酷睿Ultra9
        (r'i[3579]-?\d+\w*', 'cpu'),     # i7-14700HX
        (r'锐龙\s*\S*', 'cpu'),          # 锐龙7
        (r'(\d+)g[bd]', 'ram'),           # 32G/16GB
        (r'(\d+)t[bd]', 'storage'),       # 1T/1TB
        (r'(\d+)g[bd]\s*ssd', 'storage'),
    ]

    @staticmethod
    def parse(title: str) -> dict:
        brand = ''
        for b in DigitalMatcher.BRANDS:
            if b in title:
                brand = b
                break
        # 系列型号：系列词表匹配（耀世16Ultra / 暗影精灵Max16 / 战66）
        _re = re
        SERIES_WORDS = ['耀世', '暗影精灵', '光影精灵', '拯救者', '天选', '灵越',
                        '星Book', '星book', '战66', '战99', '小新', 'ThinkPad',
                        'thinkpad', 'Yoga', 'yoga', 'OMEN', 'omen', '暗影', '蛟龙', '极光']
        series = ''
        for w in SERIES_WORDS:
            m = _re.search(w + r' ?[A-Za-z0-9]{0,12}', title, _re.I)
            if m:
                series = m.group(0)
                # 截断：遇到 GPU/CPU 关键词就停（避免吞掉配置数字）
                cut = _re.search(r'(?i)(rtx\s*\d|gtx\s*\d|酷睿|锐龙|i[3579]-?\d|u\s*\d|amd|intel)', series)
                if cut:
                    series = series[:cut.start()]
                # 清理尾部连续 3-4 位数字组（GPU 列表：5060 5070ti 5080）与孤立 CPU 代号（U9/i7）
                series = _re.sub(r'(?i)(\s+\d{3,4}[a-z]?)+$', '', series.strip())
                series = _re.sub(r'(?i)\s+[a-z]\d+$', '', series.strip())
                break
        # 兜底：品牌后 2-6 字
        if not series:
            m2 = _re.search(r'[一-龥]{2,6}\d{0,3}[A-Za-z]{0,6}', title)
            series = m2.group(0) if m2 else ''

        config = {}
        low = title.lower()
        for pat, key in DigitalMatcher.CONFIG_PATTERNS:
            m2 = _re.search(pat, low)
            if m2:
                config[key] = m2.group(0)
        # 纯数字 GPU 兜底（WorkBuddy 建议）："耀世16 Ultra 5080" → gpu=5080
        # 排除内存/硬盘数字（32G/1T 已匹配 ram/storage），只认 4 位 GPU 型号
        if 'gpu' not in config:
            m3 = _re.search(r'(?:^|[^\d])(50[5-9]0|50[5-9]0\s*ti)(?=$|[^\d])', title, _re.I)
            if m3:
                config['gpu'] = m3.group(1).replace(' ', '').lower()
        return {'brand': brand, 'series': series, 'config': config}

    @staticmethod
    def key(item: dict) -> str:
        p = item.get('parsed', {})
        # 同品牌+同系列归一化即同组（配置差异用标题展示，跨平台对比优先）
        brand = p.get('brand', '')
        series = DigitalMatcher._norm(p.get('series', ''))
        return f'{brand}|{series}'

    @staticmethod
    def _norm(s: str) -> str:
        """系列名归一化：去空格、小写（耀世16Ultra == 耀世16 Ultra）"""
        return s.replace(' ', '').replace('-', '').lower()[:25]

# ========== 适配器注册 ==========

ADAPTERS = {
    '服饰': ClothingMatcher,
    '食品': FoodMatcher,
    '日用百货': FoodMatcher,  # 日用规格化商品暂用食品规则（品牌+规格）
    '数码家电': DigitalMatcher,
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
