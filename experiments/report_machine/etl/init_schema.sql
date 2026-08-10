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

-- 15. 同花顺一级板块涨幅排名 + 板块内涨幅前5个股（由 stg_ths_member + stg_tencent_snapshot 计算）
--     板块涨幅 = 流通市值加权 Σ(个股权重×个股涨幅)，权重=流通市值（文档要求自由流通市值，快照以流通市值近似）
--     个股并列排序：涨跌幅 → 成交额 → 换手率 → 流通市值（文档次级因子中封单量/封板时间快照无数据，用后三者）
DROP TABLE IF EXISTS mid_ths_sector_top5;
CREATE TABLE mid_ths_sector_top5 (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_time       TEXT NOT NULL,        -- 取数时间
    trade_date       TEXT NOT NULL,        -- 交易日
    sector_ts_code   TEXT NOT NULL,        -- 板块代码
    sector_name      TEXT,                 -- 板块名称
    sector_type      TEXT,                 -- 板块类型 I行业/N概念/TH特色/R地域/BB宽基/S风格统计/ST风格因子
    sector_cat       TEXT,                 -- 同花顺一级分类：行业/概念/特色/地域/综合
    sector_rank      INTEGER,              -- 板块涨幅排名（流通市值加权涨幅降序）
    sector_chg_pct   REAL,                 -- 板块涨幅（流通市值加权）
    sector_avg_chg_pct REAL,               -- 板块平均涨幅（简单平均，参考）
    member_count     INTEGER,              -- 总成分股数
    valid_count      INTEGER,              -- 有效快照数
    up_count         INTEGER,              -- 上涨家数
    limit_up_count   INTEGER,              -- 涨停家数
    sector_amount_wan REAL,                -- 板块总成交额（万元）
    stock_rank       INTEGER,              -- 板块内个股排名 1~5
    stock_ts_code    TEXT,                 -- 个股代码
    stock_name       TEXT,                 -- 个股名称
    stock_chg_pct    REAL,                 -- 个股涨跌幅%
    stock_amount_wan REAL,                 -- 个股成交额（万元）
    stock_turnover_rate REAL,              -- 个股换手率%
    stock_mv_flow    REAL,                 -- 个股流通市值（亿元）
    is_limit_up      INTEGER,              -- 是否涨停（price >= limit_up-0.005）
    etl_time         TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_top5_time ON mid_ths_sector_top5(fetch_time);
CREATE INDEX IF NOT EXISTS idx_top5_sector ON mid_ths_sector_top5(sector_ts_code);
CREATE INDEX IF NOT EXISTS idx_top5_rank ON mid_ths_sector_top5(sector_rank);

-- ========================== 累积型贴源表(2026-08-06 新增) ==========================
-- 注意: 以下表为【存量+增量累积型】(回填历史 + 每日增量), 用 CREATE TABLE IF NOT EXISTS,
--       init_schema() 重跑时【不重建、不清数据】(与上方按天重建的表不同)

-- 16. 券商评级与盈利预测(stg_report_rc, 接口 report_rc, 每晚19~22点更新)
CREATE TABLE IF NOT EXISTS stg_report_rc (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,            -- 股票代码
    name        TEXT,                     -- 股票名称
    report_date TEXT NOT NULL,            -- 研报日期 YYYYMMDD
    report_title TEXT,                    -- 报告标题
    report_type TEXT,                     -- 报告类型
    classify    TEXT,                     -- 报告分类
    org_name    TEXT NOT NULL,            -- 机构名称
    author_name TEXT,                     -- 作者
    quarter     TEXT NOT NULL,            -- 预测报告期 如 2026Q4
    op_rt       REAL,                     -- 预测营业收入(万元)
    op_pr       REAL,                     -- 预测营业利润(万元)
    tp          REAL,                     -- 预测利润总额(万元)
    np          REAL,                     -- 预测净利润(万元)
    eps         REAL,                     -- 预测每股收益(元)
    pe          REAL,                     -- 预测市盈率
    rd          REAL,                     -- 预测股息率
    roe         REAL,                     -- 预测净资产收益率
    ev_ebitda   REAL,                     -- 预测EV/EBITDA
    rating      TEXT,                     -- 卖方评级
    max_price   REAL,                     -- 预测最高目标价
    min_price   REAL,                     -- 预测最低目标价
    imp_dg      TEXT,                     -- 机构关注度
    create_time TEXT,                     -- TS数据更新时间
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, report_date, org_name, quarter)
);
CREATE INDEX IF NOT EXISTS idx_report_rc_code ON stg_report_rc(ts_code);
CREATE INDEX IF NOT EXISTS idx_report_rc_date ON stg_report_rc(report_date);

-- 17. 融资融券明细(stg_margin, 接口 margin_detail, 每天8:30更新T-1)
CREATE TABLE IF NOT EXISTS stg_margin (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,            -- 交易日期
    ts_code     TEXT NOT NULL,            -- TS股票代码
    name        TEXT,                     -- 股票名称
    rzye        REAL,                     -- 融资余额(元)
    rqye        REAL,                     -- 融券余额(元)
    rzmre       REAL,                     -- 融资买入额(元)
    rqyl        REAL,                     -- 融券余量(股)
    rzche       REAL,                     -- 融资偿还额(元)
    rqchl       REAL,                     -- 融券偿还量(股)
    rqmcl       REAL,                     -- 融券卖出量(股,份,手)
    rzrqye      REAL,                     -- 融资融券余额(元)
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(trade_date, ts_code)
);
CREATE INDEX IF NOT EXISTS idx_margin_code ON stg_margin(ts_code);
CREATE INDEX IF NOT EXISTS idx_margin_date ON stg_margin(trade_date);

-- 18. 龙虎榜(stg_top_list, 接口 top_list, 当日17:30后更新)
CREATE TABLE IF NOT EXISTS stg_top_list (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date  TEXT NOT NULL,            -- 交易日期
    ts_code     TEXT NOT NULL,            -- TS代码
    name        TEXT,                     -- 名称
    close       REAL,                     -- 收盘价
    pct_change  REAL,                     -- 涨跌幅
    turnover_rate REAL,                   -- 换手率
    amount      REAL,                     -- 总成交额
    l_sell      REAL,                     -- 龙虎榜卖出额
    l_buy       REAL,                     -- 龙虎榜买入额
    l_amount    REAL,                     -- 龙虎榜成交额
    net_amount  REAL,                     -- 龙虎榜净买入额
    net_rate    REAL,                     -- 龙虎榜净买额占比
    amount_rate REAL,                     -- 龙虎榜成交额占比
    float_values REAL,                    -- 当日流通市值
    reason      TEXT,                     -- 上榜理由
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(trade_date, ts_code, reason)   -- 同一股同一天可多条(不同上榜理由)
);
CREATE INDEX IF NOT EXISTS idx_top_list_code ON stg_top_list(ts_code);
CREATE INDEX IF NOT EXISTS idx_top_list_date ON stg_top_list(trade_date);

-- 19. 大宗交易(stg_block_trade, 接口 block_trade)
CREATE TABLE IF NOT EXISTS stg_block_trade (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,            -- TS代码
    trade_date  TEXT NOT NULL,            -- 交易日期
    price       REAL,                     -- 成交价
    vol         REAL,                     -- 成交量(万股)
    amount      REAL,                     -- 成交金额(万元)
    buyer       TEXT,                     -- 买方营业部
    seller      TEXT,                     -- 卖方营业部
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, trade_date, price, vol, buyer, seller)
);
CREATE INDEX IF NOT EXISTS idx_block_trade_code ON stg_block_trade(ts_code);
CREATE INDEX IF NOT EXISTS idx_block_trade_date ON stg_block_trade(trade_date);

-- 20. 十大流通股东(stg_top10_floatholder, 接口 top10_floatholders, 季度披露)
CREATE TABLE IF NOT EXISTS stg_top10_floatholder (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,            -- TS股票代码
    ann_date    TEXT,                     -- 公告日期
    end_date    TEXT NOT NULL,            -- 报告期 YYYYMMDD
    holder_name TEXT NOT NULL,            -- 股东名称
    hold_amount REAL,                     -- 持有数量(股)
    hold_ratio  REAL,                     -- 占总股本比例(%)
    hold_float_ratio REAL,                -- 占流通股本比例(%)
    hold_change REAL,                     -- 持股变动
    holder_type TEXT,                     -- 股东类型
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, end_date, holder_name)
);
CREATE INDEX IF NOT EXISTS idx_top10_code ON stg_top10_floatholder(ts_code);
CREATE INDEX IF NOT EXISTS idx_top10_date ON stg_top10_floatholder(end_date);

-- 21. 北向持股(stg_hk_hold, 接口 hk_hold, 2024-08-20起季度披露)
CREATE TABLE IF NOT EXISTS stg_hk_hold (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT,                     -- 原始代码
    trade_date  TEXT NOT NULL,            -- 交易日期
    ts_code     TEXT NOT NULL,            -- TS代码
    name        TEXT,                     -- 股票名称
    vol         INTEGER,                  -- 持股数量(股)
    ratio       REAL,                     -- 持股占比(%)
    exchange    TEXT,                     -- SH沪股通/SZ深股通/HK港股通
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_hk_hold_code ON stg_hk_hold(ts_code);
CREATE INDEX IF NOT EXISTS idx_hk_hold_date ON stg_hk_hold(trade_date);

-- 22. 筹码分布-每日汇总(stg_cyq_perf, 接口 cyq_perf, 每天18~19点更新)
CREATE TABLE IF NOT EXISTS stg_cyq_perf (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,            -- 股票代码
    trade_date  TEXT NOT NULL,            -- 交易日期
    his_low     REAL,                     -- 历史最低价
    his_high    REAL,                     -- 历史最高价
    cost_5pct   REAL,                     -- 5分位成本
    cost_15pct  REAL,                     -- 15分位成本
    cost_50pct  REAL,                     -- 50分位成本
    cost_85pct  REAL,                     -- 85分位成本
    cost_95pct  REAL,                     -- 95分位成本
    weight_avg  REAL,                     -- 加权平均成本
    winner_rate REAL,                     -- 胜率
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_cyq_perf_code ON stg_cyq_perf(ts_code);
CREATE INDEX IF NOT EXISTS idx_cyq_perf_date ON stg_cyq_perf(trade_date);

-- 23. 筹码分布-分价位(stg_cyq_chips, 接口 cyq_chips, 每天18~19点更新)
CREATE TABLE IF NOT EXISTS stg_cyq_chips (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT NOT NULL,            -- 股票代码
    trade_date  TEXT NOT NULL,            -- 交易日期
    price       REAL,                     -- 成本价格
    percent     REAL,                     -- 价格占比(%)
    etl_time    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(ts_code, trade_date, price)
);
CREATE INDEX IF NOT EXISTS idx_cyq_chips_code ON stg_cyq_chips(ts_code);
CREATE INDEX IF NOT EXISTS idx_cyq_chips_date ON stg_cyq_chips(trade_date);

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
