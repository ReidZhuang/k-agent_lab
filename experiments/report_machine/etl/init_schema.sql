-- =============================================================================
-- 盘中数据报告 — SQLite 数据库建表脚本
-- 两层架构: 贴源层 (stg_) + 中间层 (mid_)
-- 数据库文件: /home/stockagent/project_space/database/report_market.db
-- =============================================================================

-- ========================== 贴源层 ==========================

-- 1. 东方财富概念板块成分（个股→板块索引）
DROP TABLE IF EXISTS stg_dc_member;
CREATE TABLE stg_dc_member (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日 YYYYMMDD
    ts_code     TEXT NOT NULL,           -- 板块代码 BKxxxx.DC
    con_code    TEXT NOT NULL,           -- 成分股代码
    con_name    TEXT,                    -- 成分股名称
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_dc_member_date ON stg_dc_member(trade_date);
CREATE INDEX IF NOT EXISTS idx_dc_member_code ON stg_dc_member(ts_code);
CREATE INDEX IF NOT EXISTS idx_dc_member_con  ON stg_dc_member(con_code);

-- 2. 同花顺概念板块成分
DROP TABLE IF EXISTS stg_ths_member;
CREATE TABLE stg_ths_member (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,           -- 板块代码 xxxxxx.TI
    con_code    TEXT NOT NULL,           -- 成分股代码
    con_name    TEXT,                    -- 成分股名称
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_ths_member_code ON stg_ths_member(ts_code);
CREATE INDEX IF NOT EXISTS idx_ths_member_con  ON stg_ths_member(con_code);

-- 3. 通达信概念板块成分
DROP TABLE IF EXISTS stg_tdx_member;
CREATE TABLE stg_tdx_member (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日 YYYYMMDD
    ts_code     TEXT NOT NULL,           -- 板块代码 xxxxxx.TDX
    con_code    TEXT NOT NULL,           -- 成分股代码
    con_name    TEXT,                    -- 成分股名称
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tdx_member_date ON stg_tdx_member(trade_date);
CREATE INDEX IF NOT EXISTS idx_tdx_member_code ON stg_tdx_member(ts_code);
CREATE INDEX IF NOT EXISTS idx_tdx_member_con  ON stg_tdx_member(con_code);

-- 4. 东方财富概念板块分类（板块名称映射）
DROP TABLE IF EXISTS stg_dc_index;
CREATE TABLE stg_dc_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日
    ts_code     TEXT NOT NULL,           -- 板块代码 BKxxxx.DC
    name        TEXT,                    -- 板块名称
    idx_type    TEXT,                    -- 板块类型（概念板块/行业板块/地域板块）
    leading     TEXT,                    -- 领涨股票名称
    leading_code TEXT,                   -- 领涨股票代码
    pct_change  REAL,                    -- 涨跌幅
    up_num      INTEGER,                 -- 上涨家数
    down_num    INTEGER,                 -- 下跌家数
    total_mv    REAL,                    -- 总市值（万元）
    turnover_rate REAL,                  -- 换手率
    level       TEXT,                    -- 行业层级
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_dc_index_date ON stg_dc_index(trade_date);
CREATE INDEX IF NOT EXISTS idx_dc_index_code ON stg_dc_index(ts_code);

-- 5. 同花顺概念板块分类
DROP TABLE IF EXISTS stg_ths_index;
CREATE TABLE stg_ths_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,           -- 板块代码 xxxxxx.TI
    name        TEXT,                    -- 板块名称
    count       INTEGER,                 -- 成分个数
    exchange    TEXT,                    -- 交易所
    list_date   TEXT,                    -- 上市日期
    type        TEXT,                    -- N概念指数 S特色指数
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_ths_index_code ON stg_ths_index(ts_code);

-- 6. 通达信概念板块分类
DROP TABLE IF EXISTS stg_tdx_index;
CREATE TABLE stg_tdx_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日
    ts_code     TEXT NOT NULL,           -- 板块代码 xxxxxx.TDX
    name        TEXT,                    -- 板块名称
    idx_type    TEXT,                    -- 板块类型（概念板块/行业板块/风格板块/地区板块）
    idx_count   INTEGER,                 -- 成分个数
    total_share REAL,                    -- 总股本(亿)
    float_share REAL,                    -- 流通股(亿)
    total_mv    REAL,                    -- 总市值(亿)
    float_mv    REAL,                    -- 流通市值(亿)
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tdx_index_date ON stg_tdx_index(trade_date);
CREATE INDEX IF NOT EXISTS idx_tdx_index_code ON stg_tdx_index(ts_code);

-- 7. 东方财富概念板块日行情
DROP TABLE IF EXISTS stg_dc_daily;
CREATE TABLE stg_dc_daily (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日
    ts_code     TEXT NOT NULL,           -- 板块代码
    close       REAL,                    -- 收盘点位
    open        REAL,                    -- 开盘点位
    high        REAL,                    -- 最高点位
    low         REAL,                    -- 最低点位
    change      REAL,                    -- 涨跌点位
    pct_change  REAL,                    -- 涨跌幅
    vol         REAL,                    -- 成交量(股)
    amount      REAL,                    -- 成交额(元)
    swing       REAL,                    -- 振幅
    turnover_rate REAL,                  -- 换手率
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_dc_daily_date ON stg_dc_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_dc_daily_code ON stg_dc_daily(ts_code);

-- 8. 同花顺概念板块日行情
DROP TABLE IF EXISTS stg_ths_daily;
CREATE TABLE stg_ths_daily (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,           -- 板块指数代码
    trade_date  TEXT NOT NULL,           -- 交易日
    close       REAL,                    -- 收盘点位
    open        REAL,                    -- 开盘点位
    high        REAL,                    -- 最高点位
    low         REAL,                    -- 最低点位
    pre_close   REAL,                    -- 昨日收盘点
    avg_price   REAL,                    -- 平均价
    change      REAL,                    -- 涨跌点位
    pct_change  REAL,                    -- 涨跌幅
    vol         REAL,                    -- 成交量（手）
    turnover_rate REAL,                  -- 换手率（%）
    total_mv    REAL,                    -- 总市值（元）
    float_mv    REAL,                    -- 流通市值（元）
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_ths_daily_date ON stg_ths_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_ths_daily_code ON stg_ths_daily(ts_code);

-- 9. 通达信概念板块日行情
DROP TABLE IF EXISTS stg_tdx_daily;
CREATE TABLE stg_tdx_daily (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,           -- 交易日
    ts_code     TEXT NOT NULL,           -- 板块代码
    close       REAL,                    -- 收盘点位
    open        REAL,                    -- 开盘点位
    high        REAL,                    -- 最高点位
    low         REAL,                    -- 最低点位
    pre_close   REAL,                    -- 昨日收盘点
    change      REAL,                    -- 涨跌点位
    pct_change  REAL,                    -- 涨跌幅%
    vol         REAL,                    -- 成交量（手）
    amount      REAL,                    -- 成交额（万元）
    vol_ratio   REAL,                    -- 量比
    turnover_rate REAL,                  -- 换手%
    swing       REAL,                    -- 振幅%
    up_num      INTEGER,                 -- 上涨家数
    down_num    INTEGER,                 -- 下跌家数
    limit_up_num INTEGER,                -- 涨停家数
    limit_down_num INTEGER,              -- 跌停家数
    total_share REAL,                    -- 总股本(亿)
    float_share REAL,                    -- 流通股(亿)
    float_mv    REAL,                    -- 流通市值(亿)
    pe          REAL,                    -- 市盈率
    pb          REAL,                    -- 市净率
    etl_time    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tdx_daily_date ON stg_tdx_daily(trade_date);
CREATE INDEX IF NOT EXISTS idx_tdx_daily_code ON stg_tdx_daily(ts_code);

-- 10. 腾讯财经 A 股全量快照（盘中/午间）
--     保留接口返回的全部字段（下标 0-53），含冗余字段，供未来扩展
DROP TABLE IF EXISTS stg_tencent_snapshot;
CREATE TABLE stg_tencent_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time      TEXT NOT NULL,        -- 取数时间戳
    ts_code         TEXT NOT NULL,        -- TS 代码（如 600000.SH）
    -- 以下为腾讯财经接口原始字段（按下标排列），空字段也保留列位置
    market_type     INTEGER,              -- [0] 市场类型（1=上海/深圳，51=创业板）
    name            TEXT,                 -- [1] 股票名称
    symbol          TEXT,                 -- [2] 6位股票代码
    price           REAL,                 -- [3] 当前价格
    prev_close      REAL,                 -- [4] 昨收价
    open            REAL,                 -- [5] 开盘价
    volume          INTEGER,              -- [6] 成交量（百股）
    outer_disc      INTEGER,              -- [7] 外盘（主动买，手）
    inner_disc      INTEGER,              -- [8] 内盘（主动卖，手）
    bid1_price      REAL,                 -- [9] 买一价
    bid1_vol        INTEGER,              -- [10] 买一量（手）
    bid2_price      REAL,                 -- [11] 买二价
    bid2_vol        INTEGER,              -- [12] 买二量（手）
    bid3_price      REAL,                 -- [13] 买三价
    bid3_vol        INTEGER,              -- [14] 买三量（手）
    bid4_price      REAL,                 -- [15] 买四价
    bid4_vol        INTEGER,              -- [16] 买四量（手）
    bid5_price      REAL,                 -- [17] 买五价
    bid5_vol        INTEGER,              -- [18] 买五量（手）
    ask1_price      REAL,                 -- [19] 卖一价
    ask1_vol        INTEGER,              -- [20] 卖一量（手）
    ask2_price      REAL,                 -- [21] 卖二价
    ask2_vol        INTEGER,              -- [22] 卖二量（手）
    ask3_price      REAL,                 -- [23] 卖三价
    ask3_vol        INTEGER,              -- [24] 卖三量（手）
    ask4_price      REAL,                 -- [25] 卖四价
    ask4_vol        INTEGER,              -- [26] 卖四量（手）
    ask5_price      REAL,                 -- [27] 卖五价
    ask5_vol        INTEGER,              -- [28] 卖五量（手）
    field_29        TEXT,                 -- [29] 空字段（预留）
    time_stamp      TEXT,                 -- [30] 日期时间 YYYYMMDDHHMMSS
    chg             REAL,                 -- [31] 涨跌额
    chg_pct         REAL,                 -- [32] 涨跌幅（%）
    high            REAL,                 -- [33] 最高价
    low             REAL,                 -- [34] 最低价
    amount_detail   TEXT,                 -- [35] 成交额/成交量详情（原始值）
    volume_dup      INTEGER,              -- [36] 成交量（手，重复 fields[6]）
    amount_wan      REAL,                 -- [37] 成交额（万元）
    turnover_rate   REAL,                 -- [38] 换手率（%）
    pe              REAL,                 -- [39] 市盈率（动态）
    field_40        TEXT,                 -- [40] 空字段（预留）
    high_dup        REAL,                 -- [41] 最高价（重复 fields[33]）
    low_dup         REAL,                 -- [42] 最低价（重复 fields[34]）
    amplitude       REAL,                 -- [43] 振幅（%）
    market_cap_flow REAL,                 -- [44] 流通市值（亿元）
    market_cap_total REAL,                -- [45] 总市值（亿元）
    pb              REAL,                 -- [46] 市净率
    limit_up        REAL,                 -- [47] 涨停价
    limit_down      REAL,                 -- [48] 跌停价
    volume_ratio    REAL,                 -- [49] 量比
    diff_weicha     REAL,                 -- [50] 委差
    avg_price       REAL,                 -- [51] 均价
    pe_dynamic      REAL,                 -- [52] 动态市盈率
    pe_static       REAL,                 -- [53] 静态市盈率
    etl_time        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_snapshot_time ON stg_tencent_snapshot(fetch_time);
CREATE INDEX IF NOT EXISTS idx_snapshot_code ON stg_tencent_snapshot(ts_code);

-- ========================== 中间层 ==========================

-- 11. 东方财富盘中板块行情（由 stg_dc_member + stg_tencent_snapshot 计算）
DROP TABLE IF EXISTS mid_sector_dc;
CREATE TABLE mid_sector_dc (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time      TEXT NOT NULL,        -- 取数时间
    trade_date      TEXT NOT NULL,        -- 交易日
    ts_code         TEXT NOT NULL,        -- 板块代码
    name            TEXT,                 -- 板块名称
    member_count    INTEGER,              -- 总成分股数
    valid_count     INTEGER,              -- 有效价格数
    avg_chg_pct     REAL,                 -- 平均涨跌幅
    max_chg_pct     REAL,                 -- 板块内最大涨幅
    min_chg_pct     REAL,                 -- 板块内最大跌幅
    up_count        INTEGER,              -- 上涨家数
    down_count      INTEGER,              -- 下跌家数
    total_amount    REAL,                 -- 总成交额（万元）
    total_mv        REAL,                 -- 总市值（万元）
    turnover_rate   REAL,                 -- 平均换手率
    etl_time        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_mid_dc_time ON mid_sector_dc(fetch_time);
CREATE INDEX IF NOT EXISTS idx_mid_dc_code ON mid_sector_dc(ts_code);

-- 12. 同花顺盘中板块行情（由 stg_ths_member + stg_tencent_snapshot 计算）
DROP TABLE IF EXISTS mid_sector_ths;
CREATE TABLE mid_sector_ths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time      TEXT NOT NULL,        -- 取数时间
    trade_date      TEXT NOT NULL,        -- 交易日
    ts_code         TEXT NOT NULL,        -- 板块代码
    name            TEXT,                 -- 板块名称
    member_count    INTEGER,              -- 总成分股数
    valid_count     INTEGER,              -- 有效价格数
    avg_chg_pct     REAL,                 -- 平均涨跌幅
    max_chg_pct     REAL,                 -- 板块内最大涨幅
    min_chg_pct     REAL,                 -- 板块内最大跌幅
    up_count        INTEGER,              -- 上涨家数
    down_count      INTEGER,              -- 下跌家数
    total_amount    REAL,                 -- 总成交额（万元）
    total_mv        REAL,                 -- 总市值（万元）
    turnover_rate   REAL,                 -- 平均换手率
    etl_time        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_mid_ths_time ON mid_sector_ths(fetch_time);
CREATE INDEX IF NOT EXISTS idx_mid_ths_code ON mid_sector_ths(ts_code);

-- 13. 通达信盘中板块行情（由 stg_tdx_member + stg_tencent_snapshot 计算）
DROP TABLE IF EXISTS mid_sector_tdx;
CREATE TABLE mid_sector_tdx (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time      TEXT NOT NULL,        -- 取数时间
    trade_date      TEXT NOT NULL,        -- 交易日
    ts_code         TEXT NOT NULL,        -- 板块代码
    name            TEXT,                 -- 板块名称
    member_count    INTEGER,              -- 总成分股数
    valid_count     INTEGER,              -- 有效价格数
    avg_chg_pct     REAL,                 -- 平均涨跌幅
    max_chg_pct     REAL,                 -- 板块内最大涨幅
    min_chg_pct     REAL,                 -- 板块内最大跌幅
    up_count        INTEGER,              -- 上涨家数
    down_count      INTEGER,              -- 下跌家数
    total_amount    REAL,                 -- 总成交额（万元）
    total_mv        REAL,                 -- 总市值（万元）
    turnover_rate   REAL,                 -- 平均换手率
    etl_time        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_mid_tdx_time ON mid_sector_tdx(fetch_time);
CREATE INDEX IF NOT EXISTS idx_mid_tdx_code ON mid_sector_tdx(ts_code);

-- 14. 个股盘中数据（宽表，供下游查询）
DROP TABLE IF EXISTS mid_stock_intraday;
CREATE TABLE mid_stock_intraday (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time      TEXT NOT NULL,        -- 取数时间
    trade_date      TEXT NOT NULL,        -- 交易日
    ts_code         TEXT NOT NULL,        -- TS 代码
    name            TEXT,                 -- 股票名称
    price           REAL,                 -- 当前价格
    prev_close      REAL,                 -- 昨收
    open            REAL,                 -- 开盘价
    high            REAL,                 -- 最高价
    low             REAL,                 -- 最低价
    chg_pct         REAL,                 -- 涨跌幅%
    turnover_rate   REAL,                 -- 换手率%
    amount_wan      REAL,                 -- 成交额（万元）
    amplitude       REAL,                 -- 振幅%
    volume          INTEGER,              -- 成交量（手）
    volume_ratio    REAL,                 -- 量比
    avg_price       REAL,                 -- 均价
    market_cap_total REAL,                -- 总市值（亿元）
    market_cap_flow REAL,                 -- 流通市值（亿元）
    pe_dynamic      REAL,                 -- 动态市盈率
    pb              REAL,                 -- 市净率
    limit_up        REAL,                 -- 涨停价
    limit_down      REAL,                 -- 跌停价
    -- 所属板块（冗余宽表，方便查询）
    dc_sectors      TEXT,                 -- 所属东方财富板块列表（逗号分隔）
    ths_sectors     TEXT,                 -- 所属同花顺板块列表
    tdx_sectors     TEXT,                 -- 所属通达信板块列表
    etl_time        TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_intraday_time ON mid_stock_intraday(fetch_time);
CREATE INDEX IF NOT EXISTS idx_intraday_code ON mid_stock_intraday(ts_code);
CREATE INDEX IF NOT EXISTS idx_intraday_date ON mid_stock_intraday(trade_date);

-- ========================== 元数据 ==========================

-- 15. 更新日志
DROP TABLE IF EXISTS meta_update_log;
CREATE TABLE meta_update_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    TEXT,                    -- 批次号
    api_name    TEXT NOT NULL,           -- 接口名称
    table_name  TEXT,                    -- 写入表名
    trade_date  TEXT,                    -- 交易日
    start_time  TEXT,                    -- 开始时间
    end_time    TEXT,                    -- 结束时间
    status      TEXT,                    -- SUCCESS/FAILED/PARTIAL
    rows_fetched INTEGER,               -- 获取行数
    rows_written INTEGER,               -- 写入行数
    error_msg   TEXT,                    -- 错误信息
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_log_batch ON meta_update_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_log_status ON meta_update_log(status);
