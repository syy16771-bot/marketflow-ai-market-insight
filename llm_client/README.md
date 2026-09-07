# MarketFlow AI LLM Client

本目录提供 OpenAI-compatible API 的最小适配层。它不改变 Prompt、Schema、确定性分析或验证规则，也不保存 API Key。

## 环境变量

```text
MOCK_MODE=true
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

- `MOCK_MODE` 默认为 `true`，此时不创建网络客户端，并继续读取 `pipeline/mock_llm_outputs/`。
- `MOCK_MODE=false` 时，另外三个变量均为必填。
- `LLM_BASE_URL` 通常填写兼容服务的 API 根路径，例如 `https://provider.example/v1`；客户端会请求 `/chat/completions`。
- Key 只从当前进程环境读取，代码和项目文件中不提供 `.env` 或默认 Key。

## 真实模式流程

```text
analysis output
  -> existing Prompt Package builder
  -> OpenAI-compatible chat completions
  -> strict JSON parsing
  -> Schema Validator
  -> Evidence Validator
  -> Consistency Checker
  -> final_report
```

商品洞察会先通过 Schema 校验。竞品与用户痛点随后通过 Schema、证据和一致性校验；只有上游结果有效时才会生成策略建议。所有结果最后还会进入 Pipeline 原有的完整验证门禁。

以下情况会抛出明确异常并停止，不生成或覆盖最终报告：

- API 响应正文不是严格 JSON
- Prompt 返回 `insufficient_evidence`
- 组件 Schema 校验失败
- evidence ID 或证据关联无效
- 确定性价格、评论频次或竞品矩阵被改写
- 最终报告 Schema 校验失败

## 当前测试边界

本阶段不发送真实 API 请求。测试使用：

```powershell
$env:MOCK_MODE = "true"
python pipeline/run_pipeline.py --all
```

真实模式仅完成接口和失败门禁，待提供服务配置后再做联调验证。
