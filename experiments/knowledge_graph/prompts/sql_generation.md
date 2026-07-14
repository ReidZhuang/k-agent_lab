# 取数代码生成

## 步骤

### Step 1: 识别接口
根据"可用字段"和"表结构"确定要调用的 API 函数名。
- tushare: pro.函数名()
- akshare: ak.函数名()
- levistock: lk.函数名()
- 腾讯/新浪: requests.get(url)

### Step 2: 字段映射
将"要取的数据"中的字段名映射到 API 返回的列名。
例如: 毛利率 → gross_profit_margin, PE_TTM → pe_ttm
映射依据是"可用字段"栏中的字段表。

### Step 3: 构造参数
- ts_code: 股票代码，格式按数据源要求
- 日期: YYYYMMDD，用 start_date/end_date 参数
- Token: 通过 os.getenv('TUSHARE_TOKEN') 读取，不要硬编码
- 长区间: 一年一段，for year in range... pd.concat()

### Step 4: 执行取数
- 只取需要的列（用 fields 参数或 DataFrame 切片）
- 直接 print() 或 print(df.to_string())
- 空结果: 返回空 DataFrame，不要编造数据
- 无时间范围: 默认取最近 20 个交易日

### Step 5: 容错
- 检查 Token 是否存在
- 参数错不盲目重试
- 说明失败原因

## 输出要求
- 只输出纯 Python 代码（无 Markdown 包裹，无额外解释）
- 不要使用 SELECT/FROM/WHERE 等 SQL 关键字
- Token 必须用 os.getenv()，不许硬编码
