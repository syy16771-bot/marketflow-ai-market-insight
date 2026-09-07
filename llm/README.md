# MarketFlow AI LLM 洞察层

本目录定义三个 LLM 阶段的输入契约、Prompt 和输出 Schema，不包含模型客户端、API Key、网络请求或推理实现。

## 目录结构

```text
llm/
├── product_insight.py
├── customer_insight.py
├── strategy_advisor.py
├── prompts/
│   ├── product_insight_prompt.md
│   ├── customer_insight_prompt.md
│   └── strategy_prompt.md
└── README.md
```

## 模块职责

| 阶段 | 输入 | 目标输出 |
| --- | --- | --- |
| 商品洞察 | `analysis` 的商品与数据集信息 | `product_analysis.schema.json` |
| 竞品与用户声音 | `analysis` 的价格、竞品、评论和信号 | 竞品 Schema 对象 + 痛点 Schema 数组 |
| 商品策略 | `analysis` 事实 + 已校验的上游洞察 | `recommendation.schema.json` 数组 |

三个 Python 模块只生成 Prompt Package：

```text
stage
system_prompt
input_data
output_schema
output_schema_path / output_schema_paths
insufficient_evidence_signal
```

它们不会发送 Prompt，也不会模拟模型输出。

## 数据流

```text
analysis 确定性输出
        ↓
商品洞察 Prompt Package
        ↓ 已通过 Schema 校验的商品分析
竞品与用户声音 Prompt Package
        ↓ 已通过 Schema 校验的竞品分析和痛点
商品策略 Prompt Package
        ↓ 已通过 Schema 校验的建议
final_report 组装
```

## 数字字段所有权

LLM 不拥有任何数字计算权：

- 价格来自 `price_analysis`
- 评论数量和平均评分来自 `review_statistics`
- 频次来自 `pain_point_signals`
- 竞品事实来自 `competitor_analysis_base.competitor_matrix`

Prompt 要求模型原样复制这些字段。后续集成层还必须用 Schema 和确定性结果做二次比对，不能只依赖 Prompt 约束。

## 结论来源类型

- 商品定位、用户画像、场景、优劣势、痛点和机会：`ai_inference`
- 策略建议：`recommendation`
- 被复制的竞品事实：`data_fact`
- 被复制的价格和频次：`calculated`

每条 AI 结论必须带 `evidence_ids` 和 `confidence`。

## 证据不足协议

正常结果必须符合目标 Schema。若缺少生成合法结果所需的最小证据，模型应只返回控制信号：

```text
insufficient_evidence
```

该信号不是报告内容，不写入 `final_report`。编排层应把对应阶段标记为未完成或部分完成，而不是让模型生成占位事实。

对于仍能形成部分合法结果的情况：

- 证据不足的竞品结论数组保持为空
- 单条评论支持的痛点标记为 `limited`
- 无证据的结论不生成
- 商品描述缺失项进入 `information_gaps`

## 后续集成边界

下一阶段如接入模型，应在独立适配层完成：

1. 调用本目录的 Package Builder
2. 将 Prompt、输入和 Schema 发送给模型
3. 识别 `insufficient_evidence`
4. 解析纯 JSON 输出
5. 使用 `schemas/` 正式校验
6. 验证所有 evidence ID 均存在
7. 对比所有不可变数字字段

本阶段不实现以上调用流程。

