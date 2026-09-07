# MarketFlow AI 确定性数据分析层

本目录将 `data/` 中的商品、竞品和评论样例转换为稳定、可追溯的结构化上下文。它不调用 LLM、API、Agent 或前端。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `price_analysis.py` | 校验竞品数据，计算最低、最高、平均和中位价格 |
| `review_analysis.py` | 校验评论数据，计算评分、评论量和关键词痛点信号 |
| `competitor_analysis.py` | 构建符合既有竞品 Schema 的事实矩阵和价格区间 |
| `output_schema.py` | 组合商品、价格、评论和竞品结果，输出 AI 上下文包 |

## 输入

每个 Demo 目录必须包含：

```text
product.json
competitors.json
reviews.csv
```

评论中的 `competitor_id` 必须存在于同一数据包的 `competitors.json`。

## 输出结构

```text
analysis_version
dataset
product_input
price_analysis
review_analysis
competitor_analysis_base
```

其中：

- `data_fact` 表示直接复制自 Demo 数据
- `calculated` 表示由确定性规则计算
- `pain_point_signals` 只是关键词命中信号，不是最终 AI 痛点结论
- `strengths`、`weaknesses` 和 `differentiation_opportunities` 暂时为空，留给后续 Agent

## 运行方式

分析一个 Demo：

```text
python analysis/output_schema.py data/portable-blender
```

检查全部 Demo：

```text
python analysis/output_schema.py data --all
```

命令只向标准输出打印 JSON，不创建结果文件。

## 输入输出示例

输入价格：`29.99、49.99、42.99 USD`

价格输出：

```json
{
  "currency": "USD",
  "minimum": 29.99,
  "maximum": 49.99,
  "average": 40.99,
  "median": 42.99,
  "sample_size": 3,
  "source_type": "calculated"
}
```

## 与既有 Schema 的关系

既有 `competitor_analysis.schema.json` 的 `price_range` 没有 `average` 字段，且本阶段禁止修改 Schema。因此：

- 完整 `price_analysis` 保留 PRD 要求的平均价格，供后续 AI 使用
- `competitor_analysis_base.price_range` 只投影 Schema 已允许的字段
- 不通过额外字段绕过 `additionalProperties: false`

## 规则边界

- 金额使用十进制定点计算并四舍五入到两位
- 评论评分 1–3 星被视为负向样本
- 痛点信号使用透明的英文关键词规则
- 同一评论可命中多个主题
- `confidence: 1` 只表示计算或复制过程确定，不代表关键词分类具有 100% 语义准确率
- 最终痛点名称、严重程度和策略建议仍应由后续 AI 阶段生成并校验

