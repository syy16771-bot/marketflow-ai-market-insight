# MarketFlow AI Streamlit 展示层

本目录只负责作品集界面，不修改确定性分析、Schema、验证规则或 LLM Client。页面优先加载已经通过验证的 `pipeline/final_report.json`。

## 页面结构

1. **分析工作台**：选择三个内置 Demo，查看或编辑商品名称、目标市场和商品描述，并启动现有 Pipeline。
2. **结果报告**：展示竞品数、评论数、高优先级痛点和建议数，以及商品分析、竞品分析、用户痛点、优化建议四个 Tab。
3. **可信度说明**：解释 Data Fact、Calculated、AI Inference、Recommendation，展示验证状态、数据来源和已知限制。

当前固定数据集只支持原始 Demo 输入。若用户编辑了商品信息，界面会停止分析并提示缺少配套证据，不会把无关竞品或评论用于新商品。

## 启动方式

项目只新增 Streamlit 这一项界面依赖。安装后在项目根目录运行：

```powershell
python -m pip install streamlit
$env:MOCK_MODE = "true"
streamlit run app/main.py
```

Mock 模式不需要 API Key。真实 LLM 模式沿用 `llm_client/README.md` 中的环境变量：

```powershell
$env:MOCK_MODE = "false"
$env:LLM_API_KEY = "<在本地终端设置，不要写入文件>"
$env:LLM_BASE_URL = "https://provider.example/v1"
$env:LLM_MODEL = "your-model"
streamlit run app/main.py
```

## 展示边界

- 不执行爬虫或实时市场搜索。
- 不绕过 Pipeline 的 Schema、Evidence 和 Consistency 门禁。
- 验证失败时只展示错误，不生成新报告。
- 页面中的乱码修复仅作用于历史演示文本的显示副本，不写回 `data/` 或报告源文件。
