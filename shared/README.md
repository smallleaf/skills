# shared — 公共工具库

## 功能

提供各技能共享的基础工具模块，避免重复代码。

## 模块说明

### `browser.py`

封装 `openclaw browser` CLI 的 Playwright 上下文管理器，提供持久化 profile 支持。

**主要接口：**

```python
from shared.browser import new_browser_context

with new_browser_context("profile_name") as (ctx, page):
    page.goto("https://example.com")
    # ... 操作页面
# Cookie 自动保存到 profile
```

**特性：**
- 持久化 Cookie（每次使用已登录状态，无需重复登录）
- 独立 profile 隔离（各技能互不干扰）
- 退出时自动保存 Cookie

## 使用方式

在技能脚本中直接 import：

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/shared"))
from browser import new_browser_context
```
