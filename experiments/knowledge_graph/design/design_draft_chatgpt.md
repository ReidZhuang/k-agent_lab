# StockAgent 信息检索知识图谱（IRKG）核心设计

## 1. 知识图谱整体定位

该知识图谱用于连接：

```
用户问题
    ↓
LLM问题拆解（需要什么信息）
    ↓
信息检索知识图谱
    ↓
数据源 / API / 网站 / 字段 / 搜索方式
    ↓
获取数据或内容
    ↓
LLM分析生成结果
```

知识图谱不负责金融知识推理，只负责：

> 根据目标信息需求，找到最佳的信息获取路径。

---

# 2. Node（节点）设计

| Node类型           | 作用                     | 示例                           | 主要属性                                         |
| ---------------- | ---------------------- | ---------------------------- | -------------------------------------------- |
| Information      | 表示需要获取的信息类别，是整个图谱的核心入口 | 行情数据、财务数据、公司公告、政策、新闻、资金流向    | name、alias、description、embedding_id          |
| Information Item | 表示具体的数据项或内容项           | ROE、PE、净利润、成交额、公告标题、政策文件     | name、alias、description、data_type             |
| Source           | 表示信息来源                 | Tushare、Wind、巨潮资讯、东方财富、政府官网  | name、type、url、official、need_login、need_token |
| Access Method    | 表示获取方式                 | SQL、REST API、网页搜索、RSS、MCP    | name、description                             |
| Endpoint         | 表示具体接口、数据库表、网页检索入口     | daily_basic、moneyflow、公告搜索接口 | name、path、request_type、parameter             |
| Field            | 表示具体数据库字段或返回字段         | pe、pb、roe、close、amount       | name、data_type、unit、description              |
| Search Template  | 表示网页搜索规则               | site:gov.cn + 创新药 + 政策文件     | keyword_template、sort_rule                   |
| Task（可选）         | 表示LLM拆解后的任务类型          | 查询公司公告、查询资金流向                | name、alias、description                       |

---

# 3. Node详细设计

## 3.1 Information节点

示例：

| 属性           | 示例            |
| ------------ | ------------- |
| name         | 财务数据          |
| alias        | 财务指标、基本面数据    |
| description  | 企业经营和盈利能力相关数据 |
| embedding_id | vector_001    |

---

## 3.2 Information Item节点

示例：

| 属性        | 示例                  |
| --------- | ------------------- |
| name      | ROE                 |
| alias     | 净资产收益率、股东回报率        |
| type      | financial_indicator |
| data_type | float               |
| unit      | %                   |

---

## 3.3 Source节点

示例：

| 属性          | 示例                  |
| ----------- | ------------------- |
| name        | Tushare             |
| type        | Financial API       |
| url         | https://tushare.pro |
| official    | True                |
| need_token  | True                |
| description | A股金融数据接口            |

---

## 3.4 Endpoint节点

示例：

| 属性           | 示例             |
| ------------ | -------------- |
| name         | fina_indicator |
| type         | API            |
| source       | Tushare        |
| request_type | REST           |
| frequency    | Quarterly      |

---

## 3.5 Field节点

示例：

| 属性          | 示例             |
| ----------- | -------------- |
| name        | roe            |
| table       | fina_indicator |
| data_type   | float          |
| description | 净资产收益率         |

---

# 4. Relationship（关系）设计

| Relationship   | 方向                             | 含义         | 示例                     |
| -------------- | ------------------------------ | ---------- | ---------------------- |
| belongs_to     | Information Item → Information | 数据项属于某类信息  | ROE → 财务数据             |
| provided_by    | Information Item → Source      | 某来源提供该信息   | ROE → Tushare          |
| best_source    | Information → Source           | 某类信息最佳来源   | 公司公告 → 巨潮资讯            |
| accessed_by    | Source → Access Method         | 数据源访问方式    | Tushare → REST API     |
| implemented_by | Access Method → Endpoint       | 获取方式对应具体接口 | REST API → daily_basic |
| returns        | Endpoint → Field               | 接口返回字段     | daily_basic → pe       |
| search_by      | Source → Search Template       | 网站搜索方式     | 政府官网 → site搜索          |
| fallback_to    | Source → Source                | 备用数据源关系    | 巨潮资讯 → 东方财富            |
| validate_by    | Information → Source           | 信息验证来源     | 公告 → 巨潮资讯              |

---

# 5. Relationship属性设计（重点）

数据时效性、可信度等信息放在关系属性中。

原因：

同一个Source对于不同Information，其能力不同。

例如：

东方财富：

* 实时行情：优秀
* 财务数据：一般
* 官方公告：次优

因此这些属性属于：

```
Information
    ↓
Source
```

这条关系。

---

## Relationship属性

| 属性                  | 含义     | 示例       |
| ------------------- | ------ | -------- |
| priority            | 推荐优先级  | 100      |
| authority_score     | 权威程度   | 95       |
| freshness_score     | 数据更新速度 | 90       |
| coverage_score      | 覆盖范围   | 100      |
| stability_score     | 稳定程度   | 95       |
| cost_score          | 获取成本   | 100      |
| searchability_score | 搜索便利程度 | 90       |
| update_frequency    | 更新频率   | 实时/每日/季度 |
| latency             | 数据延迟   | 5分钟      |
| reliability_score   | 综合可靠度  | 95       |

---

# 6. 示例完整链路

## 示例1：查询公司ROE

用户问题：

```
分析宁德时代盈利能力
```

LLM拆解：

```
需要：
ROE
净利润
营业收入
```

知识图谱：

```
ROE
 |
 | provided_by
 |
Tushare
 |
 | accessed_by
 |
REST API
 |
 | implemented_by
 |
fina_indicator
 |
 | returns
 |
roe
```

最终返回：

```
数据源：
Tushare

接口：
fina_indicator

字段：
roe
```

---

## 示例2：查询公司公告

用户问题：

```
宁德时代最近有什么重大公告？
```

LLM拆解：

```
需要：
公司公告
```

知识图谱：

```
公司公告

    |
    | best_source
    |
巨潮资讯

    |
    | search_by
    |
公告搜索模板
```

返回：

```
网站：
巨潮资讯

搜索方式：
股票代码 + 最近30天公告
```

---

# 7. 推荐的数据查询逻辑

最终检索流程：

```
LLM输出Information需求

        ↓

Information节点匹配

        ↓

查询所有Source关系

        ↓

根据Relationship属性评分排序

        ↓

选择最高优先级Source

        ↓

获取Endpoint/API/SearchTemplate

        ↓

执行数据获取

        ↓

返回LLM分析
```

---

# 8. 核心设计原则

1. Knowledge Graph不保存金融知识，只保存"如何获取知识"。

2. Information是核心入口。

3. Source不是重点，Source提供什么能力才是重点。

4. 数据质量、时效性、可信度属于关系属性，不建立独立Node。

5. LLM负责理解问题和分析结果，Graph负责检索路径决策。

6. Graph的目标输出必须是可执行的信息获取方案：

```
数据源
+
接口
+
表
+
字段

或者：

网站
+
URL
+
搜索关键词
+
搜索方式
```
