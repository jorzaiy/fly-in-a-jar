---
inclusion: always
---

# 仓库结构与约定

```
fly-in-a-jar/
├─ .kiro/
│  ├─ specs/fly-brain-horror/   requirements / design / tasks / story / fragment-guide / research / kiroween-rules
│  ├─ steering/                 本目录：产品、技术、结构、片段约定
│  └─ hooks/                    自动跑校验和测试的 hook
├─ app/
│  ├─ main.py      FastAPI 入口（启动时校验内容，失败拒绝启动）
│  ├─ api/         路由、请求校验、限流
│  ├─ engine/      state.py（状态模型）、commands.py（系统指令）、rules.py（规则引擎）、turn.py（回合流程，待写）
│  ├─ judge/       base.py、jev.py、mock.py、state_text.py（状态 → 英文描述）
│  ├─ brain/       LIF 模拟器、刺激组/读出组（待写）
│  ├─ narrator/    放电 → 故事要素 → 片段挑选与拼接（待写）
│  ├─ content/     loader.py（加载与校验）、schema.py（共享词表）
│  └─ static/      index.html、terminal.css、terminal.js（待写）
├─ content/        world.yaml、ui.yaml、fragments/*.yaml、validate.py（CLI 入口）
├─ config/         rules.yaml（判定阈值、同化率增量）、brain_map.yaml（待写）
├─ data/           预处理后的连接组 + DATA_LICENSE.md
├─ scripts/        fetch_data / preprocess / calibrate / bench / jev_probe（待写）
└─ tests/          pytest
```

## 共享词表

行动类别、失败原因、怪物/异象/劫持 key、结局、同化率档位都定义在 `app/content/schema.py`。片段 key、Jev 的 Choice 选项和引擎共用这一份，新增时只改这里，不要在别处另写字符串列表。

## 文档语言

- `.kiro/specs/` 和 `.kiro/steering/`：中文，风格是短句、直接、用表格；术语和代码标识符保留英文。
- `README.md`、代码注释、提交信息、比赛提交材料：英文。
- 片段文本：中英两版各自独立写好，不逐字翻译。

## Spec 工作流

- 需求、设计、任务分别在 `requirements.md`、`design.md`、`tasks.md`。实现前先找到对应的需求编号和设计章节。
- `tasks.md` 的勾选只反映**已验证**的完成状态：测试通过、手动核实过。标 👤 的任务需要用户本人操作，不能代勾。部署类任务（17.x）只有在线上实测后才能勾。
- 规则或需求有变化时，先改 spec，再改代码。

## 当前进度

#[[file:.kiro/specs/fly-brain-horror/tasks.md]]
