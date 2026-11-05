# 设计文档：果蝇脑驱动的文字恐怖游戏（v2）

> 对应需求：[requirements.md](./requirements.md)
> 片段写作指南（给 Gemini 用）：[fragment-guide.md](./fragment-guide.md)
> 完整剧本（剧情设定集）：[story.md](./story.md)
> v2 变更：同化率替代理智值、感官投喂、指令劫持、机房终端、第四结局、JEV 双关。

## 1. 总览

```
浏览器（自制 HTML 模拟终端）
   │  HTTPS，每回合一次 POST，请求里带完整游戏状态
   ▼
Caddy（fly.luckall.de，自动证书）
   ▼
FastAPI（单进程，Docker 容器）
   ├─ api/        路由、请求校验、限流
   ├─ engine/     回合流程：指令解析 → 劫持 → 判定 → 状态更新 → 模拟 → 叙事
   ├─ judge/      Jev 判定器 + 本地 mock 判定器
   ├─ brain/      LIF 模拟器（进程池，2 个 worker，各自常驻连接组）
   ├─ narrator/   放电结果 → 故事要素 → 片段选择与拼接
   └─ content/    世界设定、片段库、界面文本的加载与校验
```

服务端不保存会话。每回合浏览器把状态发过来，服务端算完新状态再发回去（需求 9.4）。

**JEV 双关：** 剧情里判定你的声音叫 JEV（一种嗜神经病毒的研究所代号）；代码里判定器始终是 TypeSafe 的 Jev API。同名是有意为之，不要在实现上混淆：病毒是叙事外衣，API 是真实依赖。

## 2. 关键技术决策

| 决策 | 选择 | 理由 | 放弃的方案 |
|------|------|------|-----------|
| 模拟器 | 自己用 numpy 写事件驱动 LIF，参数照搬 Shiu et al. 2024 | 只依赖 numpy，可控、好调试 | Brian2 太重；flypoke 许可证待核实 |
| 连接组规模 | 只保留 ≥5 个突触的连接（约 270 万条），阈值可配置 | 文件 15–30 MB，可直接放 GitHub | 全部 1500 万条约 150 MB，原型用不上 |
| 每回合脑状态 | 每回合从静息态重新模拟 | 无状态、可复现 | 跨回合保留电压：状态太大 |
| 前端终端 | 自写 HTML+CSS+原生 JS | 中文输入法和逐字打字好处理 | xterm.js 对中文 IME 支持有坑 |
| 片段格式 | YAML | Gemini 好写、人好改 | JSON 多行转义易错 |
| 并发 | ProcessPoolExecutor(max_workers=2) + 排队 | 模拟受 GIL，必须多进程 | 线程池无法并行 |
| 片段挑选 | 用放电数取模，不用随机数 | 故事完全由果蝇脑决定 | random.choice 引入脑外因素 |
| 指令劫持用哪回合的脑 | 用上一回合的读出 | 不破坏无状态、可复现；避免为劫持再跑一次模拟 | 本回合预模拟：翻倍开销 |
| 感官投喂 | 只改输入放电倾向，输出仍由连接组决定 | 保住"真实大脑不可预测"的卖点 | 动作直接决定结果：大脑退化成按钮 |

## 3. 世界设定

完整设定见 [story.md](./story.md)。定稿后机器可读的部分写进 `content/world.yaml`。下面只列实现要点。

**场景（8 个）：** reception、corridor、fly_room、prep_room、em_room、server_room、cold_storage、exit（结局）。连接关系见 story.md 第三章地图。

**物品（17 个）：** flashlight、earplugs、visitor_log、cryo_gloves、sugar_cube、vial、vial_fly（由 vial 变成）、co2_pad、scalpel、ethanol、slide_4096、recorder、keycard、lighter、usb_drive、fuse、sample_box、notebook_page。初始位置、名称、用途见 story.md 第三、四章。

**标志（flags）：** power_on、light_on、ears_plugged、server_burned、caught_fly（本局抓过果蝇，第四结局要求全程为 false）、read_usb、saw_slide。

**物品使用规则（代码执行，写在 world.yaml）：**

| 规则 ID | 条件 | 效果 |
|---------|------|------|
| `fuse_frostbite` | 冷库拿 fuse 但没戴 cryo_gloves | 拿不到，同化率 +5 |
| `keycard_tangled` | 电镜室拿 keycard 但没 scalpel | 拿不到 |
| `restore_power` | 机房用 fuse | 设 power_on，消耗 fuse |
| `escape` | 前台用 keycard 且 power_on | 结局 escaped |
| `light` | 用 flashlight | 设 light_on，视觉异象 −1 档 |
| `plug_ears` | 用 earplugs | 设 ears_plugged，声音异象 −1 档 |
| `bait` | 用 sugar_cube | monster_block=2，消耗方糖 |
| `catch_fly` | 怪物在场用 vial | vial→vial_fly，设 caught_fly |
| `stun` | 怪物在场用 co2_pad | monster_stunned=2，消耗麻醉垫 |
| `scare` | 怪物在场用 lighter | 怪物退走 |
| `firewall` | 持 ethanol+lighter，用 ethanol | monster_block=4，消耗乙醇 |
| `read_log` | 用 visitor_log | 线索 4 |
| `play_recorder` | 用 recorder | 线索 8 |
| `open_box` | 用 sample_box | 线索 10，同化率 +5 |
| `read_usb` | 机房用 usb_drive 且 power_on | 线索 11，设 read_usb |
| `view_slide` | 电镜室用 slide_4096 且 power_on | 线索 12，设 saw_slide |
| `burn_server` | 机房持 ethanol+lighter 用在机柜上，且 read_usb | 设 server_burned，蜂群进入乱码态，monster_block=3（蜂群被压制 3 回合） |
| `absorbed` | 电镜室用显微镜，saw_slide 且同化率 ≥70 | 结局 absorbed |
| `disconnected` | server_burned 且 ears_plugged 且 caught_fly=false，前台刷卡 | 结局 disconnected |

规则 ID 也是叙事片段的 key：没给线索/结局的用 `item_use.<规则 ID>`；给线索的用 `clue.<编号>`；结局用 `ending.<结局>`。

**线索（13 条）：** 见 story.md 第六章。线索 13 是第三层反转，仅在同化率 ≥70 时才可能由 PAM 触发。

## 4. 回合流程

```
POST /api/turn {state, input}
 1. 校验：状态结构、输入 ≤200 字符、限流
 2. 解析系统指令（help/look/status/inventory/notes/lang/brainlog/restart）？
       是 → 直接处理，不消耗回合，不调 Jev，不跑模拟，返回
 3. 指令劫持判定（仅同化率 ≥70）：用上一回合读出 last_spikes + 同化率算劫持概率。
       命中 → 行动被替换为本能动作（eat/flinch/freeze），记录 hijack 信息
 4. Jev 判定（英文问题）→ verdict。失败/超时 → "裁判沉默了"，状态不变，不加同化率
 5. 按 verdict 更新状态：成功执行效果（移动/拿取/使用规则）；失败加同化率
 6. 生成刺激：行动类别 + 感官投喂倾向（含疲劳）+ 场景环境 + 危险程度
 7. 提交模拟到进程池 → 各读出组放电统计，存 last_spikes 回状态
 8. 放电 → 故事要素（怪物/异象/线索/漂移/强度）→ 更新状态（怪物、异象加同化率、线索）
 9. 怪物行为按游戏规则修正（道具、昏迷、在场、vial_fly）
10. 叙事：劫持片段 + 判定/行动片段 + 果蝇脑事件片段 → 按同化率档位选词 → 拼文本
11. 检查结局条件（同化率 100 / 各结局规则）
12. 返回 {state, output[], ended}
```

第 3 步用上一回合的脑，所以第一回合不会劫持。第 5 步在第 6 步前，先知道行动成功与否才能决定刺激什么。

## 5. 果蝇脑模块（brain/）

### 5.1 数据预处理
来源：philshiu 的 `Connectivity_783.parquet`（带正负号权重）、flywire_annotations 的神经元注释表（按 cell_type 查神经元）。两者下载时核实文件名与许可。

`scripts/preprocess.py` 输出：
- `data/connectome_v783_t5.npz`：CSR（indptr int32、indices int32、weights float32），按突触前神经元分行，已乘正负号。15–30 MB。
- `data/neurons.parquet`：序号、root_id、cell_type、super_class、side。

超过 50 MB 改用 GitHub Releases（需求 3.10）。预处理在 InstaBox 上跑，产物提交仓库。

### 5.2 LIF 模型
参数照搬 Shiu et al. 2024（实现时对照 `model.py` 核实）：静息/重置 −52 mV，阈值 −45 mV，膜时间常数 20 ms，突触时间常数 5 ms，不应期 2.2 ms，突触延迟 1.8 ms，每突触权重 0.275 mV，刺激泊松频率 150 Hz（按危险程度缩放）。

事件驱动：dt 0.1 ms，每回合 250 ms（可配），2500 步。每步向量更新电压电导 → 找越阈神经元 → 从 CSR 取下游 → 权重进延迟环形缓冲（18 步后生效）。预计单回合 0.5–1 秒。泊松种子 = hash(游戏种子, 回合数)，保证可复现。

进程池：每 worker 启动加载一次 npz，两个约 200–300 MB。同时最多 2 个模拟，排队上限 8，超出返回"大脑过载"。

### 5.3 刺激映射（玩家行动 → 神经元）
Jev 把行动归类，每类对应一组 FlyWire 感觉神经元：

| 行动类别 | 刺激神经元 |
|----------|------------|
| eat | 甜味 GRN(Gr5a) 或苦味 GRN(Gr66a) |
| smell | 嗅觉受体神经元 ORN |
| listen/talk | 江氏器 JO |
| look/light | 光感受器 R7/R8 或 R1–6 |
| touch/take/use | 机械感受神经元 |
| attack/move | 光感受器 + 机械感受 |
| hide/wait | 不额外刺激 |

**感官投喂倾向（新）：** 某些具体动作在类别之外，额外抬高指定通路的泊松频率，但**不保证**输出。实现：`config/brain_map.yaml` 的 `feeding` 表把动作关键词（敲桌、含糖、频闪、转圈）映射到 (通路, 倍率)。倍率乘进该通路刺激神经元的泊松频率。

**疲劳：** 状态里 `stim_fatigue: {pathway: count}` 记录连续使用。同一通路每连续使用一次，倍率按 0.6 衰减，换别的通路后清零。疲劳让"连续敲桌"失效甚至反噬，符合 GF 适应性。

再叠加场景环境刺激（冷库→冷感神经元，机房→JO）和危险程度（放大泊松频率）。细胞类型名写在 `config/brain_map.yaml`，实现时在 neurons.parquet 核实，找不到换最接近的。

### 5.4 读出映射（放电 → 故事要素）

| 故事要素 | 选项 ← 读出组 |
|----------|---------------|
| 怪物行为 | attack←GF；approach←P9；retreat←MDN；feed←MN9；absent←都未过阈 |
| 异象类型 | visual←LC；sound←JO 下游；smell←侧角神经元；memory←MBON；none |
| 线索 | yes←PAM 多巴胺过阈 |
| 漂移 | drift←中央复合体 EPG 放电异常（低概率） |
| 强度 | 所有读出组放电总数，分位数分 0–3 档 |

**选择规则：** 每组放电数除以校准基线得归一化值，同一要素取最高且 >1 的选项，都不超则取"无"。全"无"即死寂事件。

**怪物行为修正（按顺序）：** ①monster_block>0 → absent；②monster_stunned>0 → attack/feed 改 retreat；③怪物不在场 → attack/feed 改 approach、retreat 改 absent；④持 vial_fly → attack 改 approach。大脑日志显示原始→修正，如 `monster=ATTACK→APPROACH (vial_fly)`。

**同化率变化：** monster.attack 和强度 2–3 的异象通过片段的 `effects.sync` 增加同化率（范围 −5 到 +12，负值是罕见的"短暂清醒"）。

**线索选择：** PAM 过阈时，从未发现的果蝇脑线索挑一条，优先当前场景相关、其次编号最小。线索 13 需同化率 ≥70。全发现后给 `clue.generic`。

**校准：** `scripts/calibrate.py` 在 InstaBox 跑数百次各类刺激，取各读出组放电数第 75 百分位作基线写进配置，使各选项出现频率均衡。

### 5.5 大脑日志格式
```
[JUDGE] feasible 12% · reason=missing_item · danger 2/3 · sync 43%
[BRAIN] stimulus  Gr5a ×42 @150Hz · R7/R8 ×80 @60Hz · cold(ambient) ×12
[BRAIN] spikes    GF 3 · P9 41 · MDN 0 · MN9 2 · LC 18 · MBON 7 · PAM 9 · EPG 22
[BRAIN] decided   monster=APPROACH  anomaly=VISUAL(2)  clue=YES(#10)  drift=no
```
暗绿色等宽。`[JUDGE]` 在叙事前，`[BRAIN]` 在叙事后。细胞类型名不翻译，只有标题行中英切换。同化率 ≥50 时 `[BRAIN]` 偶尔混入 `[HOST]` 行，暗示在读你的大脑。

## 6. Jev 判定模块（judge/）

### 6.1 问题集（全英文）
| ID | 类型 | 内容 |
|----|------|------|
| feasible | Noul | Can the player perform this action now, given scene/inventory/world rules? |
| reason | Choice | physically_impossible / missing_item / no_such_target / against_world_rules / not_an_action / feasible |
| category | Choice | look move take use eat smell listen touch light attack hide wait talk other |
| target | Choice | 动态生成：出口、可见物品、场景设施、背包物品、monster、none |
| danger | Score | 0 safe / 1 risky / 2 dangerous / 3 suicidal |

### 6.2 发给 Jev 的 state（英文）
场景、出口、可见物品、背包、怪物状态、同化率、世界规则、最近 5 条行动，玩家原始输入（可能中文）附在末尾。

### 6.3 判定规则
| 可行概率 p | 结果 | 效果 |
|------------|------|------|
| p ≥ 0.65 | 成功 | 执行效果，同化率不变 |
| 0.40 ≤ p < 0.65 | 勉强成功 | 执行效果，同化率 +3 |
| p < 0.40 | 失败 | 不执行，同化率 += 5 + 危险分×3 |

阈值和增量写在 `config/rules.yaml`。成功效果由代码按 category+target 执行，Jev 不决定效果。

### 6.4 调用细节
官方 SDK `typesafe-sdk`（`TypeSafeClient().system_one(state, questions)`），字段对照官方文档核实。超时 6 秒不重试。`JUDGE=mock` 用关键词 mock 判定器。每日上限可配（默认 5000），超限切 mock 并告警。

## 7. 叙事模块（narrator/）

### 7.1 本回合文本组成
```
[劫持片段]    hijack.<本能>（仅指令劫持命中时）
[判定片段]    verdict_fail.<reason> / verdict_partial / action.<category>
              触发物品规则时用 item_use.<规则 ID> 代替 action
[物品线索]    clue.<编号>（物品规则给出线索时）
[移动片段]    scene_enter.<scene> + 系统行列出出口与物品（移动或漂移时）
[怪物片段]    monster.<behavior>（absent 时无）
[异象片段]    anomaly.<type>（none 时无）
[线索片段]    clue.<编号>（果蝇脑给出线索时）
[死寂片段]    silence（所有果蝇脑事件为"无"时，替代怪物与异象）
```

### 7.2 片段挑选
1. 按类别+key 找候选。2. 过滤不满足 requires（场景/物品/标志/怪物在场/同化率档）。3. 过滤本局已用（全用过则清空该类别记录）。4. 按强度匹配：优先同强度，否则最接近。5. 剩下的用"决定该要素的读出组放电数 mod 候选数"选一个。6. 找不到回退 `<category>.generic`。

### 7.3 同化率档位选词
片段可选带 `tiers`：为关键片段（opening、ending、anomaly、scene_enter）提供 human / latent / instinct 三档文本。选词时按当前同化率档取对应文本，缺某档则回落到 human。其余片段只有单档，普通呈现。**不要求所有片段都写三档**，控制写作量。

### 7.4 片段效果
片段可带 effects：`sync: +4`、`set_flag`、`give_item`。选中后执行，使线索片段能真正把线索/物品交给玩家。

## 8. 内容模块（content/）
```
content/
├─ world.yaml        场景、出口、设施、物品、使用规则、结局条件
├─ ui.yaml           界面文本（中英）
└─ fragments/
   ├─ opening.yaml  scene_enter.yaml  verdict.yaml  monster.yaml
   ├─ anomaly.yaml  clue.yaml  item_use.yaml  hijack.yaml
   ├─ drift.yaml  silence.yaml  ending.yaml
```
启动时 `content/validate.py` 校验（需求 5.3），另提供 `python -m content.validate`：检查必填字段、ID 唯一、中英齐全、requires/effects 引用存在、每类×强度覆盖率、三档片段的档位完整性。

## 9. 游戏状态
localStorage 保存，每回合发送，Pydantic 校验，上限 16 KB。
```yaml
version: 2
seed: 834201
turn: 12
lang: en
brainlog: true
scene: cold_storage
items: [flashlight, lighter, cryo_gloves]
taken: [flashlight, lighter, cryo_gloves]
flags: [light_on]
sync: 43               # 同化率 0–100，100 = consumed
monster_near: true
monster_block: 0
monster_stunned: 0
caught_fly: false
last_spikes: {GF: 3, P9: 41, MDN: 0, MN9: 2, LC: 18, MBON: 7, PAM: 9, EPG: 22}
stim_fatigue: {mechano: 1}
clues_found: [1, 6]
used_fragments: [m_approach_03, an_vis_11]
recent_actions: [{text: "open freezer", result: ok}]
ended: null            # escaped / consumed / absorbed / disconnected
```

## 10. API
| 方法与路径 | 请求 | 响应 |
|------------|------|------|
| POST /api/new | {lang} | {state, output} |
| POST /api/turn | {state, input} | {state, output, ended} |
| GET /api/health | — | {ok, judge, queue} |

`output` 有序数组，每项 `{kind, text}`，kind ∈ narrative/system/judge/brainlog/hijack/error，前端按 kind 决定颜色和是否逐字打出。错误码 400/429/503 都显示成游戏内提示。限流：每 IP 每分钟 20 回合，内存计数。

## 11. 前端
单页：index.html + terminal.js + terminal.css，无框架无构建。上方滚动输出区，底部 `> ` 加透明 `<input>`（中文 IME 可用）。逐字打出只对 narrative（约 40 字/秒，回车或空格跳过）。请求中显示"神经元正在放电……"并锁输入。全部用 textContent 插入。首次选语言（默认 English），localStorage 续局。黑底、琥珀叙事、暗绿脑日志、红错误、紫色劫持行、CRT 扫描线。同化率 ≥70 时整体轻微抖动/泛红，强化本能接管的观感。

## 12. 部署
```
docker-compose.yml
├─ app     python:3.12-slim，uvicorn 单进程，内含 2 个模拟 worker；restart: unless-stopped
└─ caddy   caddy:2，80/443；Caddyfile：fly.luckall.de → app:8000
```
TYPESAFE_API_KEY 放 VPS 上 `.env`（已 gitignore）。日志每回合一行 JSON（turn_ms/judge_ms/queue_ms/sim_ms/spikes_total/judge_mode），不记 key 和玩家原文。部署：VPS 上 `git pull && docker compose up -d --build`。你需先把 `fly.luckall.de` 的 A 记录指向 VPS 并开放 80/443。

## 13. 仓库结构
```
fly-in-a-jar/
├─ .kiro/            spec 和 steering（不进 gitignore）
├─ app/  main.py  api/ engine/ judge/ brain/ narrator/ content/  static/
├─ content/  world.yaml ui.yaml fragments/
├─ config/  brain_map.yaml rules.yaml
├─ data/  预处理连接组 + DATA_LICENSE.md
├─ scripts/  fetch_data.py preprocess.py calibrate.py bench.py jev_probe.py
├─ Dockerfile docker-compose.yml Caddyfile .env.example LICENSE README.md
```

## 14. 错误处理
Jev 超时/错 → "裁判沉默了"，状态不变不加同化率。Jev 超每日上限 → 切 mock 告警。模拟队列满 → 503 "大脑过载"。worker 崩 → 进程池重建，本回合报错状态不变。状态无效 → 400 提示 restart。片段校验失败 → 拒绝启动，列出出错 ID。某类无候选 → 用 generic。

## 15. 验证（不额外写测试套件）
- `python -m content.validate`：校验 + 覆盖率
- `scripts/bench.py`：单回合 <3 秒，在 VPS 实测
- 可复现：同种子+同输入在 mock 下跑两次输出一致
- mock 下玩通 4 个结局
- 真 Jev 测 20 中文 + 20 英文行动，回答待确认问题 1

## 16. 风险与待核实
| 项目 | 应对 |
|------|------|
| Shiu 参数凭记忆 | 对照 model.py 核对 |
| 细胞类型名叫法 | 预处理打印各组数量，找不到换最接近 |
| 某读出组几乎不放电 | 校准暴露后加长时长或换读出组 |
| Jev SDK 字段 | 开工第一步用真 key 发最小请求核实 |
| 指令劫持手感 | 用上一回合脑，试玩时调劫持概率曲线 |
| 同化率平衡 | 试玩校准各类事件的 sync 增量，确保一局 25–40 回合 |
| FlyWire 许可 | 下载时核实，写 data/DATA_LICENSE.md |
