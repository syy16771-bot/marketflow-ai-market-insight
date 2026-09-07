# Demo 数据说明

本目录存放 MarketFlow AI 的三个离线演示数据包。数据只用于作品集产品流程、AI 工作流和评测展示，不代表真实 Amazon、品牌或市场信息。

## 目录结构

```text
data/
├── portable-blender/
│   ├── product.json
│   ├── competitors.json
│   └── reviews.csv
├── pet-water-fountain/
│   ├── product.json
│   ├── competitors.json
│   └── reviews.csv
└── ergonomic-seat-cushion/
    ├── product.json
    ├── competitors.json
    └── reviews.csv
```

## 数据标签

- `source_type: synthetic_demo`：完全虚构的演示数据
- `dataset_version`：数据包版本，用于复现实验
- `review_id`：痛点分析引用的证据 ID
- `competitor_id`：连接竞品和评论的唯一 ID

## 使用原则

- 不将 Demo 价格、评分和评论描述成实时市场事实
- 不从少量样例推断真实市场规模或销量
- 规则层负责价格和数量计算
- AI 洞察必须引用已存在的 ID
- 后续修改数据时同步更新版本与人工评测基准

