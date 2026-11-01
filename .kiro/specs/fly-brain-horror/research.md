# 类似项目调研（GitHub）

调研日期：2026-11-01。沙箱无法直接访问 github.com，以下信息来自搜索结果摘要。许可证、更新时间、运行耗时未经核实，开工前需逐一确认。

## 结论

- **没有现成项目做完全一样的事。** 没有任何项目把"果蝇脑生成恐怖故事"和"Jev 判定玩家行为"组合在一起。
- **最接近的项目：**
  - [rootcastleco/fly-brain](https://github.com/rootcastleco/fly-brain)：命令行里输入 "sugar"/"bitter" 来刺激果蝇脑并打印放电。属于"果蝇脑 + 文字交互"，但不是游戏，也不生成故事。
  - [jkalend/jev-realms](https://github.com/jkalend/jev-realms)：用 Jev 驱动 NPC 的终端 RPG，目前只有设计稿。
- **我们的创新点：** 用真实连接组的放电模式驱动叙事，再用 Jev 当"不说话的裁判"判定行为是否可行。

## 果蝇脑模拟核心候选

| 项目 | 说明 | 适用性 |
|------|------|--------|
| [vshapenko/flypoke](https://github.com/vshapenko/flypoke) | 基于 v783 的轻量 LIF 模型，CPU 上每次试验几秒，不依赖 Brian2 | **首选**。许可证待核实 |
| [philshiu/Drosophila_brain_model](https://github.com/philshiu/Drosophila_brain_model) | Nature 2024 论文的官方实现（Brian2），数据文件为 `Connectivity_783.parquet`、`Completeness_783.csv` | 作为参数和数据的权威来源。速度可能不够每回合实时跑 |
| [snedea/flybrain](https://github.com/snedea/flybrain) | 浏览器 Web Worker 里实时跑全部 139k 个神经元 | 用作可视化参考 |
| [theflyRH/thefly-brain](https://github.com/theflyRH/thefly-brain) | 读取 v783 的单个运动神经元输出来做离散决策 | 可参考"放电 → 离散输出"的映射方法 |
| [eonsystemspbc/fly-brain](https://github.com/eonsystemspbc/fly-brain) | 有 PyTorch / GPU 版本 | 较重，作备选 |

TheMrRaGe/flybrain、chnak/flybrain 等项目用的是 MaleCNS 连接组，不是 v783，不直接适用。

## Jev 相关

- 官方 Python SDK：`typesafe-ai/typesafe-sdk-python`（`pip install typesafe-sdk`）
  - `TypeSafeClient` 从环境变量 `TYPESAFE_API_KEY` 读取 key
  - 调用方式：`.system_one(state, questions)`
  - 问题类型：`Choice`、`Score`、`Noul`（是/否概率）
- 接口（来自第三方文档，需用官方文档核对）：
  - `POST https://api.typesafe.ai/v1/systemone`，使用 Bearer 认证
  - 请求：`{"state": ..., "questions": {"<id>": {"type": "noul|choice|score", "instructions": "...", ...}}}`
  - 响应（每个问题一个结果）：
    - Noul：返回 yes 的概率
    - Choice：返回 `choice`、`confidence`、`probabilities`
    - Score：返回 `score`、`legend`、`confidence`
- 示例项目：[zeke/jev](https://github.com/zeke/jev)（附带 `sample-response.json`），[vamsikrishna2421/jev-usecases](https://github.com/vamsikrishna2421/jev-usecases)
- 注意：网上有很多仿冒的 Jev 网站，只认 typesafe-ai 官方仓库和文档。

## 浏览器终端

- [abhishekkrthakur/webterm](https://github.com/abhishekkrthakur/webterm)：FastAPI + WebSocket + xterm.js，和我们的技术栈最匹配
- 建议使用 xterm.js（MIT 许可），通过 WebSocket 逐行收发消息。不暴露真实 pty，因为 pty 有安全风险，而且我们用不上。

## 风险

1. **FlyWire 数据许可：** 有来源说是 CC BY-NC 4.0（禁止商用），也有说是 CC-BY 4.0。按非商用处理，并引用 Dorkenwald et al. 2024 和 Schlegel et al. 2024。参加黑客松属于非商用，应该没问题，但需要去 flywire.ai 确认。
2. **数据体积：** 预计几十到几百 MB，不能直接放进 git 仓库。
3. **计算耗时：** 如果每回合都用 Brian2 跑全脑，可能太慢。解决办法：选用 flypoke、缩短模拟时长，或者预计算后缓存。
4. **Jev：** 只能调托管 API，有网络延迟（据报 70–500 ms），也可能出现不可用的情况。

内容已为符合授权要求做了改写。
