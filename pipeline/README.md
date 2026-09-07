# MarketFlow AI Pipeline

本目录支持离线 Mock 和 OpenAI-compatible LLM 两种运行方式，不包含 Streamlit。

## 运行模式

- `MOCK_MODE=true`（默认）：读取现有 `mock_llm_outputs/`，不发送网络请求。
- `MOCK_MODE=false`：通过 `llm_client/` 调用模型，并使用现有 Prompt Package。

无论使用哪种模式，输出都必须通过同一套 Schema、Evidence、Consistency 和最终报告验证门禁。真实模式的环境变量及安全边界见 `llm_client/README.md`。

## 流程

```text
data
  → analysis 确定性计算
  → mock LLM outputs
  → schema / evidence / consistency validation
  → final_report.json
```

## Mock 文件

- `product_analysis.json`：三个 Demo 的商品洞察
- `customer_insight.json`：三个 Demo 的竞品洞察和用户痛点
- `strategy_output.json`：三个 Demo 的策略建议

Mock 文件以 Demo slug 为目录键；每个键对应的值才是目标 Schema 实例。这样可以复用三份 fixture 文件测试三个商品，同时不把三份报告混装成一个 `final_report`。

## 运行方式

测试三个 Demo，不写报告：

```text
python pipeline/run_pipeline.py --all
```

生成便携榨汁杯报告：

```text
python pipeline/run_pipeline.py --demo portable-blender
```

报告默认写入：

```text
pipeline/final_report.json
```

也可以通过 `--output` 指定其他单一报告路径。

## 验证闸门

每个候选结果依次经过：

1. `schema_validator`：结构、类型、必填字段和枚举
2. `evidence_validator`：证据存在性和洞察关系
3. `consistency_checker`：价格、评论量、频次和竞品一致性
4. `validate_for_final_report`：最终报告生成闸门
5. `final_report.schema.json`：完整报告再次校验

任一步失败都会抛出带阶段和字段路径的错误。Pipeline 不会创建或覆盖目标报告。

## 阶段耗时

每次运行输出毫秒级耗时：

- `analysis_ms`
- `mock_llm_ms`
- `schema_validation_ms`
- `evidence_validation_ms`
- `consistency_check_ms`
- `final_report_ms`
- `total_ms`

这些时间只代表本地小样本 Mock Pipeline，不代表未来真实模型响应时间。

## 边界

- Mock 内容只引用当前 Demo 中存在的商品、竞品和评论 ID
- 数字字段原样复制 analysis 结果
- 所有商品、品牌、价格和评论仍为虚构演示数据
- 不修改 `data/`、`schemas/`、`analysis/`、`llm/` 或 `validation/`
