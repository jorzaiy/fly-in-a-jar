# 任务清单：果蝇脑驱动的文字恐怖游戏

> 对应：[requirements.md](./requirements.md) · [design.md](./design.md) · [story.md](./story.md)
> 标记 👤 的任务需要你参与，例如提供 key、在 InstaBox 或 VPS 上操作、提供 Gemini 写的片段。
> 顺序原则：先核实风险最大的两件事（Jev 接口和模拟速度），再搭游戏逻辑，最后做界面和部署。

## 阶段 0：项目骨架

- [x] 1. 创建仓库和项目骨架
  - [x] 1.1 新建 GitHub 公开仓库 `fly-in-a-jar`，按 design.md 第 13 节建立目录结构
  - [x] 1.2 添加 `pyproject.toml` 或 `requirements.txt`：fastapi、uvicorn、pydantic v2、numpy、pyyaml、typesafe-sdk，版本全部锁定
  - [x] 1.3 添加 `.gitignore`：忽略 `.env`、原始数据目录 `data/raw/`、`__pycache__`。确认 `.kiro/` **没有**被忽略
  - [x] 1.4 添加 `.env.example`（`TYPESAFE_API_KEY=`、`JUDGE=mock`、`SIM_WORKERS=2`）和开源许可证 `LICENSE`（建议 MIT）
  - [x] 1.5 写 FastAPI 入口 `app/main.py`，只有 `GET /api/health`，能用 `uvicorn` 在本地启动
  - _需求：9.6、10.1、10.2_

## 阶段 1：核实风险

- [ ] 2. 👤 核实 Jev 接口
  - [ ] 2.1 写 `scripts/jev_probe.py`：用一个固定的英文 state 和第 6.1 节的 5 个问题（Noul、Choice×3、Score）发一次真实请求，打印完整响应
  - [ ] 2.2 👤 你在本地设置 `TYPESAFE_API_KEY` 后运行，把输出发给我（我会先帮你去掉 key）
  - [ ] 2.3 根据真实响应修正 design.md 第 6.4 节的字段名，并确认 Choice 的选项可以每回合动态生成
  - [ ] 2.4 用 5 条中文行动和 5 条英文行动做个初步试探，记录判定结果
  - _需求：6.1、6.2、2.4_

- [ ] 3. 👤 准备连接组数据
  - [ ] 3.1 写 `scripts/fetch_data.py`：下载 philshiu 仓库的 `Connectivity_783.parquet` 和 `Completeness_783.csv`，以及 flywire_annotations 的神经元注释表，存到 `data/raw/`
  - [ ] 3.2 核实 FlyWire 数据许可（CC-BY 4.0 还是 CC BY-NC 4.0），写 `data/DATA_LICENSE.md`，注明出处和三篇论文的引用
  - [ ] 3.3 写 `scripts/preprocess.py`：按突触数阈值（默认 ≥5，可配置）过滤，带正负号的权重转成 CSR，输出 `data/connectome_v783_t5.npz` 和 `data/neurons.parquet`，并打印神经元数、连接数、文件大小
  - [ ] 3.4 👤 在 InstaBox 上运行 3.1 和 3.3，把产物提交到仓库。如果单个文件超过 50 MB，改用 GitHub Releases
  - _需求：3.1、3.8–3.11_

- [ ] 4. 实现 LIF 模拟器
  - [ ] 4.1 对照 philshiu 仓库的 `model.py` 核实第 5.2 节的所有参数，把它们写进 `config/brain_map.yaml`
  - [ ] 4.2 实现 `app/brain/lif.py`：事件驱动的 numpy LIF，dt = 0.1 ms，支持延迟环形缓冲区、不应期和泊松输入；输入是"刺激神经元序号 + 频率"，输出是每个神经元的放电次数和首次放电时间
  - [ ] 4.3 随机数种子 = hash(游戏种子, 回合数)。同一组输入连续跑两次，确认结果完全相同
  - [ ] 4.4 写 `scripts/bench.py`：用 5 种典型刺激各跑 10 次，打印平均耗时和内存峰值
  - [ ] 4.5 👤 分别在 InstaBox 和 2 核 4 GB 的 VPS 上运行 bench。如果单回合超过 3 秒，依次尝试：缩短模拟时长、提高突触阈值、改用预计算缓存
  - _需求：3.2–3.7、9.3_

- [ ] 5. 检查点：Jev 和模拟器都核实可行。如果其中任何一个不可行，先停下来和你商量调整方案，再继续

## 阶段 2：果蝇脑 ↔ 故事

- [ ] 6. 刺激组和读出组
  - [ ] 6.1 在 `config/brain_map.yaml` 中按第 5.3、5.4 节写好每个刺激组和读出组对应的 FlyWire 细胞类型
  - [ ] 6.2 实现 `app/brain/groups.py`：启动时用 `neurons.parquet` 把细胞类型名解析成神经元序号，并打印每组找到的神经元数量。如果有组一个都没找到，就拒绝启动
  - [ ] 6.3 逐组核对数量，把找不到或数量不合理的类型换成最接近的类型，并在配置文件里注明原因
  - _需求：3.3、3.4、7.3_

- [ ] 7. 校准读出阈值
  - [ ] 7.1 写 `scripts/calibrate.py`：遍历所有行动类别、场景环境和危险程度的组合，各跑若干次，统计每个读出组放电数的分布
  - [ ] 7.2 取第 75 百分位作为基线写回配置，同时打印每个故事要素各选项的出现频率
  - [ ] 7.3 👤 在 InstaBox 上运行。如果某个选项几乎从不出现（低于 3%），调整模拟时长或换一个读出组，然后重跑
  - _需求：4.1_

## 阶段 3：游戏内容与规则

- [x] 8. 世界数据与内容加载
  - [x] 8.1 根据 story.md 写 `content/world.yaml`：场景、出口、设施、物品初始位置、中英文名称、物品使用规则（design.md 第 3 节的规则表，含 burn_server、absorbed、disconnected）和四种结局条件
  - [x] 8.2 写 `content/ui.yaml`：所有系统文本的中英文版本，包括帮助、状态、错误提示和大脑日志标题
  - [x] 8.3 实现 `app/content/loader.py` 和 `python -m content.validate`：按 design.md 第 8 节校验，输出出错的片段 ID 和覆盖率表
  - [x] 8.4 写一套**占位片段**（每个类别和 key 各 1 个，含 hijack 和四个结局，内容简短），让游戏在 Gemini 的片段到位之前就能完整跑通
  - _需求：5.1–5.5、2.3_

- [ ] 9. 游戏状态与规则引擎
  - [x] 9.1 实现 `app/engine/state.py`：用 Pydantic 定义第 9 节的状态模型，带版本号，大小上限 16 KB
  - [x] 9.2 实现系统指令：`help` `look` `status` `inventory` `notes` `lang` `brainlog` `restart`。这些指令不消耗回合，不调用 Jev，也不跑模拟
  - [x] 9.3 实现 `app/engine/rules.py`：执行移动、拿取、使用的效果，以及物品使用规则、同化率变化、`monster_block` 和 `monster_stunned` 的倒计时、四种结局判定
  - [ ] 9.4 实现怪物行为修正（design.md 第 5.4 节的 4 条规则），并保留修正前后的结果，供大脑日志显示
  - [ ] 9.5 实现感官投喂和疲劳（design.md 第 5.3 节）：投喂动作抬高通路放电倾向，`stim_fatigue` 递减，换通路重置
  - [ ] 9.6 实现指令劫持（design.md 第 4 节第 3 步）：同化率 ≥70 时用 `last_spikes` 和同化率算概率，命中则替换行动为本能动作，产出 hijack 信息
  - [ ] 9.7 实现机房终端固定问答（`status`/`kill -9 specimen_F`/`stimulate PAM`）和瓶中之蝇的当前回合反映
  - _需求：8.1–8.5、6.4、6.5、11.1–11.7_

- [ ] 10. Jev 判定器
  - [x] 10.1 实现 `app/judge/state_text.py`：把游戏状态转成第 6.2 节格式的英文描述
  - [ ] 10.2 实现 `app/judge/jev.py`：5 个问题、动态生成的 `target` 选项、超时 6 秒、阈值判定（`config/rules.yaml`）
  - [x] 10.3 实现 `app/judge/mock.py`：中英文关键词规则，返回结构和 Jev 完全相同的结果
  - [ ] 10.4 实现每日调用上限，超出后自动切换到 mock 并在日志中告警
  - [x] 10.5 Jev 超时或报错时返回"裁判沉默了"，状态不变，也不增加同化率
  - _需求：6.1–6.8、9.10_

- [ ] 11. 叙事模块
  - [ ] 11.1 实现 `app/narrator/elements.py`：读出组放电统计 → 故事要素（归一化、取最大值、"无"选项、死寂事件、强度分档、线索选择）
  - [ ] 11.2 实现 `app/narrator/select.py`：按第 7.2 节挑选片段（条件过滤、去重、强度匹配、放电数取模、回退到 generic），并执行片段的 `effects`
  - [ ] 11.3 实现 `app/narrator/compose.py`：按第 7.1 节的顺序拼出本回合的输出，替换 `{target}` 占位符，进入场景时附上出口和物品列表
  - [ ] 11.4 实现大脑日志（第 5.5 节格式），包括怪物行为修正前后的对比，以及同化率 ≥50 偶现的 `[HOST]` 行
  - [ ] 11.5 实现同化率分档选词（第 7.3 节）：关键片段按三档取文本，缺档回落 human
  - _需求：4.1–4.5、7.1–7.5、11.3、11.4_

## 阶段 4：接口与界面

- [ ] 12. 回合流程与 API
  - [ ] 12.1 实现 `app/engine/turn.py`：按 design.md 第 4 节的 10 个步骤串起整个回合
  - [ ] 12.2 实现模拟进程池：每个 worker 启动时加载一次连接组，同时运行的模拟不超过 2 个，最多排队 8 个，超出返回 503
  - [ ] 12.3 实现 `POST /api/new`、`POST /api/turn`，并完善 `GET /api/health`（返回判定模式和队列长度）
  - [ ] 12.4 输入校验（输入不超过 200 字符，状态不超过 16 KB）；按 IP 限流，每分钟 20 个回合
  - [ ] 12.5 每回合输出一行 JSON 日志，记录各阶段耗时，不记录 key 和玩家原文
  - _需求：8.1、9.2、9.5、9.7–9.11_

- [ ] 13. 前端模拟终端
  - [ ] 13.1 写 `app/static/index.html`、`terminal.css`、`terminal.js`：滚动的输出区，底部是提示符加透明的 `<input>`，支持中文输入法
  - [ ] 13.2 按 `kind` 显示不同颜色；叙事文本逐字打出，按回车或空格可以跳过
  - [ ] 13.3 请求进行中显示"神经元正在放电……"并锁定输入；把 400、429、503 和网络错误都显示成游戏内的提示
  - [ ] 13.4 首次打开时选择语言（默认 English）；游戏状态存在 `localStorage`，刷新页面后能继续上一局
  - [ ] 13.5 所有文本都用 `textContent` 插入。加上黑底、琥珀色文字和 CRT 扫描线效果
  - _需求：1.1–1.6、2.1、2.2_

- [ ] 14. 检查点：本地用 mock 判定器完整玩通 4 个结局；触发一次指令劫持和一次感官投喂疲劳；同一种子加同一串输入跑两次，输出完全一致

## 阶段 5：正式内容

- [ ] 15. 👤 接入 Gemini 写的片段
  - [ ] 15.1 👤 你把 Gemini 写好的 YAML 文件发给我
  - [ ] 15.2 放进 `content/fragments/`，替换占位片段，运行校验并修正格式问题（内容问题会先问你）
  - [ ] 15.3 检查覆盖率表，列出缺少的类别、key 和强度，交给 Gemini 补写
  - _需求：5.1–5.5_

- [ ] 16. 👤 用真实 Jev 试玩调优
  - [ ] 16.1 👤 用真实 Jev 测试 20 条中文行动和 20 条英文行动，记录判定是否合理
  - [ ] 16.2 根据结果调整问题措辞、判定阈值和同化率增量
  - [ ] 16.3 👤 你完整玩 2–3 局，确认每局 25–40 回合（约 15–25 分钟）、难度合适、恐怖感到位
  - _需求：2.4、6.3、8.4_

## 阶段 6：部署与提交

- [ ] 17. 👤 部署到 VPS
  - [ ] 17.1 写 `Dockerfile`、`docker-compose.yml`（app + caddy，`restart: unless-stopped`）和 `Caddyfile`（`fly.luckall.de`）
  - [ ] 17.2 👤 在 `luckall.de` 的 DNS 中添加 `fly` 的 A 记录，指向 2 核 4 GB VPS 的 IP；开放 80 和 443 端口
  - [ ] 17.3 👤 在 VPS 上装好 Docker，`git clone` 仓库，创建 `.env`，运行 `docker compose up -d --build`
  - [ ] 17.4 在线上确认：HTTPS 证书正常、单回合耗时、内存占用低于 1.5 GB、重启容器后能自动恢复
  - _需求：9.1–9.12_

- [ ] 18. 👤 比赛提交
  - [x] 18.1 对照 Kiroween 2026 的正式规则，核实提交要求（`.kiro` 目录、视频时长、许可证等），结果见 [kiroween-rules.md](./kiroween-rules.md)
  - [ ] 18.2 写 README：玩法、架构图、果蝇脑和 Jev 的分工、本地运行方法、数据来源与论文引用
  - [ ] 18.3 👤 录制少于 3 分钟的演示视频，重点展示大脑日志和"果蝇脑决定故事"的过程；公开上传到 YouTube，不用未授权的音乐
  - [ ] 18.4 👤 在 2026-12-04 14:00（太平洋时间）之前，在 Devpost 上提交：类别选 Frankenstein，填游戏网址、YouTube 链接、GitHub 链接和英文的 Kiro 使用说明
  - _需求：10.1–10.7_
