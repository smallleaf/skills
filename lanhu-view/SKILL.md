---
name: lanhu-view
description: 蓝湖原型需求分析与测试用例生成。当用户提供蓝湖分享链接（lanhuapp.com/link）并要求提取需求、分析原型、生成测试用例、进行质量闭环时触发。整合了蓝湖截图抓取、需求识别、测试用例设计全链路。
---

# lanhu-view — 蓝湖需求提取 & 测试用例生成

## 执行流程

### Step 0：环境检查

```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')" 2>/dev/null || echo "MISSING"
```

- ✅ OK：直接进入 Step 1
- ❌ MISSING：执行 `pip install playwright && playwright install chromium`

### Step 1：抓取蓝湖截图

```bash
python3 ~/.openclaw/workspace/skills/lanhu-view/scripts/lanhu_view.py \
  --url "<蓝湖分享链接>" \
  --password "<访问密码>" \
  --output /tmp/lanhu_view
```

完成后输出：
- `/tmp/lanhu_view/screenshots/` — 各页截图（PNG，按侧边栏顺序编号）
- `/tmp/lanhu_view/index.json` — 页面列表（name / depth / screenshot）

**注意**：
- 自动跳过含「弃用/废弃/deprecated/旧版」的页面
- 使用持久化 profile `lanhu_view`（non-headless，避免卡死）
- profile 路径：`~/.openclaw/workspace/.browser_profiles/lanhu_view`

### Step 2：图像识别提取需求

读取 `index.json`，按顺序用 `read` 工具读每张截图，识别：

1. **页面拆分**：以截图实际内容为准，有几个页面识别几个，不臆想
2. **每页提取**：
   - UI 元素（按钮、输入框、列表、标签）
   - 业务规则、交互逻辑、标注文字
   - 字段定义、限制条件、跳转关系
   - 边界值、异常情况

输出结构化 PRD：
```json
{
  "project": "项目名称",
  "pages": [
    {
      "name": "页面路径（与侧边栏一致）",
      "ui_components": ["UI元素"],
      "business_rules": ["业务规则"],
      "interactions": ["交互逻辑"],
      "edge_cases": ["边界/异常"]
    }
  ]
}
```

### Step 3：生成测试用例

基于 Step 2 的真实 PRD 内容，按以下五维度设计用例：

| 维度 | 说明 | 优先级 |
|------|------|--------|
| 正向流程 | 正常路径操作，功能符合预期 | P0 |
| 业务规则 | 核心逻辑、条件判断、资格校验 | P0 |
| 边界情况 | 边界值、临界条件、并发点击 | P1 |
| 异常逻辑 | 无网络、弱网、非法输入、权限拒绝 | P1 |
| UI 展现 | 布局、文案、样式符合设计稿 | P2 |

输出格式（XMind 脑图结构）：
```
[页面完整路径]
├── UI (P2)
│   └── [样式/布局/文案测试点]
├── 交互 (P1)
│   └── [点击/跳转/滑动测试点]
├── 功能点 (P0)
│   └── [业务规则/校验测试点]
└── 异常 (P1)
    └── [边界值/错误状态测试点]
```

### Step 4：交付

输出完整需求文档 + 测试用例，格式：

```markdown
# [项目名] 需求文档 & 测试用例

## 一、[页面名]（depth=0）
### 1.1 [子页面]（depth=1）

**需求内容：**
...

**测试用例：**
| 用例ID | 测试点 | 操作步骤 | 预期结果 | 优先级 |
|--------|--------|----------|----------|--------|
| TC-001 | ... | ... | ... | P0 |
```

## 核心约束

- **严禁盲猜**：所有内容必须来自截图真实内容
- **完整覆盖**：每条业务规则至少对应一条测试用例
- **边界必测**：出现金额/数量/时间限制，必须补充边界值测试
- **同名页面只处理一次**
- **截图用 `read` 工具读取绝对路径**
