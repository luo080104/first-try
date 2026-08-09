-- Go购 SQLite 数据库结构 v1.0
-- 数据库文件：shopping-agent/data/shopping.db

-- ========== 商品与 SKU ==========

-- 商品主表（归一化后的商品：品牌 + 系列型号）
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,              -- 品牌（归一化：机械革命）
    series TEXT NOT NULL,             -- 系列型号（归一化：耀世16 Ultra）
    category TEXT,                    -- 品类（笔记本/手机/家电…）
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_brand_series ON products(brand, series);

-- SKU 表（具体配置档位，跨平台匹配的锚点）
-- v1.1：改为通用设计，品类特有参数存 specs JSON（适配多品类）
CREATE TABLE IF NOT EXISTS skus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    specs TEXT,                           -- 品类特有参数 JSON（电脑:{"gpu":"RTX5080","ram":32}；服饰:{"款号":"466789","颜色":"白"}）
    raw_title TEXT,                       -- 原始商品标题（用于溯源）
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_skus_product ON skus(product_id);

-- ========== 价格与优惠 ==========

-- 价格历史表（每次搜索都记录，从阶段 1 开始积累！）
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER REFERENCES skus(id),     -- 匹配到的 SKU（可为空=未匹配）
    platform TEXT NOT NULL,                 -- 平台：pdd/jd/tb/dy
    item_id TEXT NOT NULL,                  -- 平台商品 ID
    title TEXT NOT NULL,                    -- 平台原始标题
    price REAL NOT NULL,                    -- 当前价（元）
    original_price REAL,                    -- 原价/划线价（可为空）
    coupon_amount REAL,                     -- 优惠券金额（0=无）
    coupon_expire TEXT,                     -- 券有效期（实时校验用）
    url TEXT,                               -- 商品链接
    queried_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_price_sku ON price_history(sku_id);
CREATE INDEX IF NOT EXISTS idx_price_item ON price_history(platform, item_id);

-- ========== 盯价清单 ==========

-- 盯价表（用户关注的商品 + 目标价，降价推送）
CREATE TABLE IF NOT EXISTS watched_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER REFERENCES skus(id),     -- 可为空（未匹配 SKU）
    title TEXT,                             -- 商品标题
    platform TEXT,                          -- 平台
    item_id TEXT,                           -- 平台商品 ID
    current_price REAL,                     -- 盯价时的价格
    target_price REAL,                      -- 目标价（低于此价推送）
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ========== 内容联动 ==========

-- 博主名单（人工维护！AI 不评判博主声誉）
CREATE TABLE IF NOT EXISTS bloggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,                 -- bilibili/zhihu/douyin
    homepage_url TEXT,
    note TEXT,                              -- 备注（为什么关注他）
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 博主推荐内容表
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blogger_id INTEGER REFERENCES bloggers(id),
    product_id INTEGER REFERENCES products(id),  -- 推荐的商品
    title TEXT NOT NULL,                    -- 内容标题
    content_url TEXT,                       -- 视频/文章链接
    published_at TEXT,                      -- 发布时间（时效过滤用：超 6 个月降权）
    is_ad INTEGER DEFAULT 0,                -- 是否广告/恰饭（标注，不删除）
    note TEXT,                              -- AI 标注：事实 vs 观点
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ========== 家庭档案 ==========

-- 家庭成员表（尺码等，服饰比价自动过滤用）
CREATE TABLE IF NOT EXISTS family_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                     -- 称呼：爸爸/妈妈/自己
    gender TEXT,                            -- 男/女
    clothes_size TEXT,                      -- 衣服尺码（M/L/XL…）
    pants_size TEXT,                        -- 裤码（可选）
    shoe_size TEXT,                         -- 鞋码（可选）
    hat_size TEXT,                          -- 帽围（可选）
    note TEXT,                              -- 特殊偏好（不穿羽绒服/过敏…）
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ========== 政策与偏好 ==========

-- 国补政策表（人工维护起步，后续再考虑自动化）
CREATE TABLE IF NOT EXISTS subsidy_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,                   -- 省份/城市
    category TEXT,                          -- 适用品类（笔记本/家电…）
    amount REAL,                            -- 补贴金额或比例
    requirements TEXT,                      -- 申领条件
    valid_from TEXT, valid_to TEXT,         -- 有效期
    source_url TEXT,                        -- 政策来源
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 用户偏好表（记忆系统：预算/品牌倾向）
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,               -- budget/brand/…
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ========== 人工录入价格（众包补盲区，OpenPrice 模式）==========

CREATE TABLE IF NOT EXISTS manual_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,                  -- 商品关键词（比价时匹配用）
    title TEXT NOT NULL,                    -- 商品名称
    platform TEXT NOT NULL,                 -- 平台：tb/pdd/jd/other
    shop_name TEXT,                         -- 店铺/渠道名
    price REAL NOT NULL,                    -- 价格
    url TEXT,                               -- 商品链接
    note TEXT,                              -- 备注（录入人/时间说明）
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_manual_keyword ON manual_prices(keyword);

-- ========== 评论情感分析缓存（避免重复调 DeepSeek）==========

CREATE TABLE IF NOT EXISTS comment_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,             -- bili/xhs/tieba
    content_id TEXT NOT NULL,           -- 视频/笔记/帖子 ID
    positive INTEGER DEFAULT 0,         -- 正面
    negative INTEGER DEFAULT 0,         -- 负面
    neutral INTEGER DEFAULT 0,          -- 中性
    ad_suspect INTEGER DEFAULT 0,       -- 软广嫌疑
    total INTEGER DEFAULT 0,
    analyzed_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sentiment ON comment_sentiment(platform, content_id);

-- ========== v4 商品库 ==========
CREATE TABLE IF NOT EXISTS product_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,              -- tb/jd/pdd/dy
    item_id TEXT NOT NULL,               -- 平台商品 ID（去重键）
    title TEXT NOT NULL,
    brand TEXT DEFAULT '',               -- 提取品牌
    series TEXT DEFAULT '',              -- 系列/型号
    category TEXT DEFAULT '',            -- 品类
    price REAL DEFAULT 0,                -- 当前价
    original_price REAL,                 -- 原价/划线价
    coupon_amount REAL DEFAULT 0,        -- 券金额
    shop_name TEXT DEFAULT '',
    sales INTEGER DEFAULT 0,             -- 销量
    url TEXT DEFAULT '',
    img TEXT DEFAULT '',                 -- 缩略图
    specs TEXT DEFAULT '{}',             -- JSON 参数
    is_ad INTEGER DEFAULT 0,
    source TEXT DEFAULT 'api',           -- api/browser/manual
    first_seen TEXT DEFAULT (datetime('now','localtime')),
    last_seen TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(platform, item_id)
);
CREATE INDEX IF NOT EXISTS idx_items_cat ON product_items(category);
CREATE INDEX IF NOT EXISTS idx_items_price ON product_items(price);
CREATE INDEX IF NOT EXISTS idx_items_brand ON product_items(brand);
CREATE INDEX IF NOT EXISTS idx_items_title ON product_items(title);
