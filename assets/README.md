# 截图准备清单

公开版当前不包含截图，避免使用占位图或伪造界面。发布前应从本地实际运行的 `MOCK_MODE=true` 页面截取以下图片：

| 文件名 | 截图内容 | 建议重点 |
| --- | --- | --- |
| `01-workbench.png` | 分析工作台 | 三个输入字段、Demo 选择、Mock 模式标识 |
| `02-report-overview.png` | 结果报告概览 | 四个指标和商品分析入口 |
| `03-pain-point-evidence.png` | 用户痛点 | 频次、严重程度、Evidence ID、置信度 |
| `04-recommendation.png` | 优化建议 | 建议类型、优先级、关联痛点和风险提示 |
| `05-trust-validation.png` | 可信度说明 | 四类来源标签和 Validation 状态 |
| `06-architecture.png` | 系统架构 | 确定性分析、LLM、Validation、报告与页面 |

## 截图要求

- 只截取实际运行页面，不制作虚构结果。
- 使用同一个 Demo 和同一次报告，避免数字前后不一致。
- 不显示终端环境变量、用户名、本地路径或任何密钥。
- 保留 Data Fact、Calculated、AI Inference、Recommendation 标签。
- 建议统一浏览器尺寸和缩放比例。
- 截图加入仓库后，再在公开 README 中引用。
