# DS_AKSHARE_SECTOR_SPOT API 调用规则

## 接口
ak.stock_board_industry_spot_em(symbol='板块名称')

## 参数
- symbol: 板块名称（如 '小金属'、'半导体'），必填参数

## 示例
```python
import akshare as ak
df = ak.stock_board_industry_spot_em(symbol='小金属')
```

## 注意
- symbol 参数不可省略
- 免 Token
