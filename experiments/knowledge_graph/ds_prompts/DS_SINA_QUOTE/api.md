## 接口
HTTP GET: http://hq.sinajs.cn/list={prefix}{code}

## 参数
- code: sh600519 或 sz300750
- **必须带 Referer 和 User-Agent 头**
- 编码: GBK，需要 r.encoding = 'gbk'

## 返回格式
数据以逗号分割：
```
var hq_str_sh600519="股票名,开盘价,昨收,当前价,最高,最低,买一,卖一,成交量,成交额..."
```
1. 去掉前缀 `var hq_str_xxx="` 和末尾的 `";`
2. 按逗号 `,` split
3. 按字段映射表中的索引取值（注意：Tencent 用 ~ 分割，Sina 用逗号分割）