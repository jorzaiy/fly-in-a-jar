---
inclusion: always
---

# 技术栈与约束

## 栈

- Python 3.12，FastAPI + uvicorn，Pydantic v2，numpy，PyYAML。版本全部锁死在 `requirements.txt`；测试依赖在 `requirements-dev.txt`（pytest、httpx）。
- 前端：自写 HTML + CSS + 原生 JS（`app/static/`），无框架、无构建步骤。不用 xterm.js（中文输入法有坑）。
- 果蝇脑：自写 numpy 事件驱动 LIF，参数照 Shiu et al. 2024。不用 Brian2。
- 判定：Jev（`typesafe-sdk`，待 tasks.md 第 2 项核实后启用）；离线用 `JUDGE=mock` 的关键词判定器。
- 部署：Docker + Caddy，2 核 4 GB VPS，`fly.luckall.de`。

## 硬约束（不要违反）

- **运行时不调用会生成文字的语言模型。** 叙事只能来自片段库。
- **无状态：** 游戏状态存在浏览器 `localStorage`，每回合随请求发送；服务端不存会话。状态上限 16 KB，带版本号。
- **可复现：** 泊松种子 = hash(游戏种子, 回合数)；片段挑选用"放电数 mod 候选数"，不用 `random`。
- **密钥：** `TYPESAFE_API_KEY` 只从环境变量读取，不得进代码、日志、前端或 steering 文件。
- **前端安全：** 所有文本用 `textContent` 插入；不暴露真实 shell/pty。
- **数据：** 原始连接组不进 git（`data/raw/` 已忽略）；预处理产物单文件 ≤50 MB，否则用 GitHub Releases。不用 Git LFS，不用收费存储。
- **性能：** 单回合模拟目标 <3 秒；常驻内存 <1.5 GB；同时运行的模拟不超过 CPU 核数。
- **`.kiro/` 不得写进 `.gitignore`**（比赛硬性要求）。

## 常用命令

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q              # 全部测试必须通过
.venv/bin/python -m content.validate       # 内容校验 + 覆盖率表，必须 0 errors
.venv/bin/python -m content.validate --mvp # 另外要求达到 MVP 覆盖目标
uvicorn app.main:app --reload              # http://127.0.0.1:8000/api/health
```

## 工作约定

- 改代码后跑 pytest；改 `content/` 后跑 `content.validate`（hooks 会自动跑，见 `.kiro/hooks/`）。
- 可调数字放 `config/*.yaml`，不要写死在代码里。
- 注释和 docstring 用英文，并引用对应的 design 章节（如 `design §6.3`）。
- 提交：小步提交，信息用 `area: 做了什么` 的英文格式（如 `engine: add hijack roll`）。
