# MarketFlow AI 结果验证层

验证层位于确定性分析与最终报告之间。它不调用模型、不修改输出，也不负责生成报告。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `schema_validator.py` | 校验 JSON Schema、必填字段、类型、枚举、常量、数组和本地 `$ref` |
| `evidence_validator.py` | 校验证据 ID、评论证据、痛点关系和建议关系 |
| `consistency_checker.py` | 校验价格、竞品矩阵、评论数量、痛点频次，并提供报告生成闸门 |

## 验证顺序

```text
候选 AI 输出
  → Schema 校验
  → Evidence 校验
  → Consistency 校验
  → 全部通过：返回 validation_summary
  → 任一失败：返回 None 和明确错误，不生成 final_report
```

## Schema 校验规则

- 必填字段必须存在
- JSON 类型必须匹配
- 枚举和常量必须匹配
- 不允许 Schema 外字段
- 字符串、数字和数组边界必须满足
- `allOf`、`anyOf`、`if/then` 必须满足
- `final_report` 使用的本地 Schema 引用可以解析

实现覆盖当前五个 Schema 使用的 Draft 2020-12 关键字，不宣称是通用 JSON Schema 引擎。

## Evidence 校验规则

- 所有 `evidence_ids` 必须存在于 analysis 原始证据索引
- 痛点证据只能引用有效 `review_id`
- 痛点中的 `competitor_ids` 必须存在
- 痛点必须覆盖其评论证据所属的竞品
- 建议关联的痛点和差异机会必须存在
- 建议证据必须与所关联洞察的证据有交集
- 只有差异机会、没有痛点关联的建议允许通过，但产生 warning

## Consistency 校验规则

- AI 输出的 `price_range` 必须与 analysis 完全一致
- 竞品矩阵必须与 analysis 完全一致，不能新增、删除或改写竞品
- 商品 ID 必须一致
- 痛点频次必须映射到唯一的 `pain_point_signal`
- 频次、等级、样本量和证据 ID 必须原样复制
- 痛点样本量必须等于 analysis 评论总数
- 如果提供报告元数据，评论数与数据集信息必须一致

## validation_summary

验证成功时返回已有最终报告 Schema 定义的结构：

```json
{
  "schema_valid": true,
  "evidence_ids_valid": true,
  "calculations_verified": true,
  "unsupported_claim_count": 0,
  "warnings": []
}
```

验证失败时返回：

```text
validation_summary = None
errors = [明确的字段路径与失败原因]
```

调用方必须将 `None` 视为禁止生成最终报告。本阶段不创建调用方或报告生成逻辑。

