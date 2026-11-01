# 片段写作指南（给 Gemini 用）

## 怎么用

1. 把下面"提示词"部分的全部内容复制给 Gemini。
2. 片段数量较多，建议分批让 Gemini 写，每次写 1–2 个文件。例如："先写 `monster.yaml`"。
3. 把 Gemini 输出的 YAML 存到仓库的 `content/fragments/` 目录下，文件名保持一致。
4. 运行 `python -m content.validate` 检查。出错的话，把报错信息贴回给 Gemini，让它修改。

世界设定如果有改动，记得同时更新下面的提示词和 `design.md` 第 3 节。

---

## 提示词（从这里开始复制）

你要为一款浏览器文字恐怖游戏《缸中之蝇》(Fly in a Jar) 写叙事片段。游戏里的事件由一只真实果蝇大脑（FlyWire 连接组）的神经放电决定，程序会根据放电结果挑选你写的片段并拼接起来。所以每个片段都必须**独立成立**，可以和其他片段以任意顺序组合。

### 世界设定

午夜，玩家是神经成像研究所里最后一个值夜班的研究助理。这家研究所把一只果蝇的大脑切成 7000 片，用电子显微镜扫描，重建出了它的每一个神经元。今晚停电，门禁锁死。楼里有某种东西在"思考"，它用的正是那只果蝇的大脑。

**怪物"蜂群"（The Swarm）：** 没有固定形态。有时是墙里的嗡嗡声，有时是一团由成千上万只果蝇聚成的人形。它好奇、饥饿，被甜味吸引，怕火。

**场景：**
- `reception` 前台 / Reception：应急灯，旋转门已锁，前台上有访客登记簿。通往 corridor，以及出口（需要门禁卡）。
- `corridor` 走廊 / Corridor：很长，地上有反光，墙上挂着神经元的显微照片，有一排挂白大褂的衣架。通往 reception、fly_room、prep_room、server_room、cold_storage。
- `fly_room` 果蝇饲养室 / Fly Room：成排的果蝇管，培养基发酵的酸甜味，管子是空的。
- `prep_room` 解剖准备室 / Prep Room：解剖显微镜，培养皿，切片刀。通往 em_room。
- `em_room` 电镜室 / EM Room：巨大的电子显微镜，真空泵的低鸣。Dr. Weiss 的尸体在这里，门禁卡在她身上。
- `server_room` 机房 / Server Room：存着连接组数据的服务器机柜，一台黑屏的终端，电闸箱里的保险丝烧了。
- `cold_storage` 冷库 / Cold Storage：零下 80 度的冰柜，结霜的地面，标着日期的样本盒。

**人物 Dr. Weiss：** 研究所的资深研究员，主持了这只果蝇大脑的切片和重建。今晚她签到进了楼，再也没出来。她倒在电镜室里，挂绳缠在机器上。

**物品：**

| ID | 中文名 | 英文名 | 在哪里 | 用途 |
|----|--------|--------|--------|------|
| `flashlight` | 手电筒 | Flashlight | 前台 | 照明 |
| `earplugs` | 耳塞 | Earplugs | 前台 | 隔绝声音 |
| `visitor_log` | 访客登记簿 | Visitor Log | 前台 | 阅读后得到线索 4 |
| `cryo_gloves` | 防冻手套 | Cryo Gloves | 走廊的白大褂衣架上 | 从 −80 ℃ 冰柜里拿东西 |
| `sugar_cube` | 方糖 | Sugar Cube | 果蝇饲养室 | 当诱饵引开蜂群 |
| `vial` | 空果蝇管 | Empty Vial | 果蝇饲养室 | 抓一只果蝇，变成 `vial_fly` |
| `vial_fly` | 装着果蝇的管子 | Vial with a Fly | 由空果蝇管变成 | 持有时蜂群不敢攻击你 |
| `co2_pad` | CO₂ 麻醉垫 | CO₂ Pad | 果蝇饲养室 | 让蜂群昏迷 |
| `scalpel` | 手术刀 | Scalpel | 解剖准备室 | 割断 Dr. Weiss 的挂绳 |
| `ethanol` | 乙醇 | Ethanol | 解剖准备室 | 和打火机一起做成火墙 |
| `slide_4096` | 第 4096 号切片 | Slide #4096 | 解剖准备室 | 在电子显微镜下观察，得到线索 12 |
| `recorder` | 录音笔 | Voice Recorder | 电镜室 | 播放后得到线索 8 |
| `keycard` | 门禁卡 | Keycard | 电镜室，Dr. Weiss 身上 | 打开前台的门 |
| `lighter` | 打火机 | Lighter | 机房 | 吓退蜂群 |
| `usb_drive` | U 盘 | USB Drive | 机房 | 供电后插入终端，得到线索 11 |
| `fuse` | 保险丝 | Fuse | 冷库的 −80 ℃ 冰柜里 | 恢复供电 |
| `sample_box` | 标着今晚日期的样本盒 | Sample Box | 冷库 | 打开后得到线索 10 |
| `notebook_page` | 笔记残页 | Notebook Page | 由线索 1 给出 | 记录已发现的线索 |

**标志（flags）：** `power_on`（已恢复供电）、`light_on`（手电筒照明中）、`ears_plugged`（戴着耳塞）。

**重要：先读完整剧本。** 写之前请先读 `story.md`，它有三层反转的真相（你其实是第 7001 号样本）、JEV 病毒设定、同化率三档、以及四个结局的正文。片段的恐怖感要建立在这套真相之上，尤其是"记忆"类异象和同化率高档位的文本。

### 文风要求

- 第二人称、现在时。中文用"你"，英文用 "you"。
- 心理恐怖为主，不写血腥细节。多写声音、气味、触感和细小的错误感。
- 偶尔埋一些果蝇神经科学的意象：复眼、触角、伸喙、嗡鸣、神经元、突触、切片。
- 每个片段 1–3 句。中文不超过 100 字，英文不超过 60 个单词。
- 中英文是**各自独立的好文字**，不要逐字翻译。英文要像母语作家写的。
- 不要提到真实存在的版权角色、品牌或作品。
- 不要替玩家做决定，也不要写"你决定……"。
- 不要在文字里给玩家物品、移动玩家或结束游戏，除非这个片段的 `effects` 里写了对应效果。
- 除非用 `requires` 限定了场景，否则不要提到具体场景里的物件。怪物片段和异象片段可能出现在任何场景。

### 格式

每个文件是一个 YAML 列表，每一项是一个片段：

```yaml
- id: monster_approach_01      # 必填。唯一，格式：<category>_<key>_<两位序号>
  category: monster            # 必填。见下方类别表
  key: approach                # 必填。见下方类别表
  intensity: 2                 # 0–3。类别表里标了"按强度"的才需要填
  requires:                    # 可选。所有条件都满足时才可能被选中
    scene: [corridor, fly_room]  # 只能在这些场景出现
    items: [flashlight]          # 玩家必须持有
    flags: [power_on]            # 必须已设置
    not_flags: [light_on]        # 必须没有设置
    monster_near: true           # 怪物必须在场（或 false：必须不在场）
  effects:                     # 可选。片段被选中后生效
    sync: 4                      # 同化率变化，范围 -5 到 +12（正数让玩家更接近被吞噬）
    give_item: notebook_page     # 给玩家一件物品
    set_flag: power_on
    clear_flag: light_on
    monster_near: true
  zh: |
    嗡鸣声停了。停得太突然，像有什么东西在屏住呼吸。
  en: |
    The humming stops. Too suddenly, like something holding its breath.
```

**同化率（sync）：** 替代传统的"理智值"，但方向相反——数值越高越糟，到 100 玩家被吞噬。坏事（被攻击、强异象、失败）用正数，罕见的"短暂清醒"才用负数。

**分档文本（可选，只给关键片段）：** 开场、结局、异象、进入场景这几类片段可以写三档文本，程序按玩家当前同化率选用。格式是把 `zh`/`en` 换成 `tiers`：

```yaml
  tiers:
    human:     # 0–30%，正常人类感官
      zh: |
        桌上的玻片盒排得很整齐。
      en: |
        The slide boxes on the bench are lined up neatly.
    latent:    # 31–69%，视觉碎成六边形，嗅觉变成趋近/排斥信号
      zh: |
        桌上有七千个反光的六边形切面，每一个里都有一只你的眼睛。
      en: |
        Seven thousand hexagonal facets glint on the bench, each holding one of your eyes.
    instinct:  # 70–99%，本能接管
      zh: |
        七千个格子。七千个位置。你知道哪一个是空着等你的。
      en: |
        Seven thousand cells. Seven thousand slots. You know which one waits empty for you.
```

缺某一档时程序回落到 `human`。其余类别只写单档（`zh`/`en`）即可，不要求全部写三档，以控制写作量。

可以使用的占位符只有一个：`{target}`，程序会把它替换成玩家行动对象的名字（自动按语言切换）。只能在 `action`、`verdict_fail` 和 `hijack` 类别中使用。

### 类别和数量

| 文件 | category | key | 按强度 | 每个 key 的数量 | 小计 | 说明 |
|------|----------|-----|--------|----------------|------|------|
| `opening.yaml` | `opening` | `default` | 否 | 3 | 3 | 开场。交代停电、被困、楼里有东西 |
| `scene_enter.yaml` | `scene_enter` | 7 个场景 ID | 否 | 3 | 21 | 进入场景时的氛围描写。**不要写出口和物品**，物品可能已被拿走，程序会根据当前状态另起一行列出 |
| `verdict.yaml` | `action` | `look` `move` `take` `use` `eat` `smell` `listen` `touch` `light` `attack` `hide` `wait` `talk` `other` | 否 | 2 | 28 | 行动成功时的描写，不要写行动的具体后果，因为后果由程序处理 |
| `verdict.yaml` | `verdict_partial` | `default` | 否 | 6 | 6 | 勉强成功：做到了，但付出了代价，比如手抖、受伤、出声 |
| `verdict.yaml` | `verdict_fail` | `physically_impossible` `missing_item` `no_such_target` `against_world_rules` `not_an_action` | 否 | 4 | 20 | 失败。语气是冷漠的、像有什么在审判你 |
| `monster.yaml` | `monster` | `attack` `approach` `retreat` `feed` | 是，0–3 各 2 个 | 8 | 32 | `attack` 要带 `sync` 正效果（如 +8），`approach` 要设 `monster_near: true`，`retreat` 要设 `monster_near: false` |
| `anomaly.yaml` | `anomaly` | `visual` `sound` `smell` `memory` | 是，0–3 各 2 个 | 8 | 32 | 异象。强度 2–3 的要带 `sync` 正效果。`memory` 是闪回、似曾相识、不属于你的记忆。**这一类建议写三档（tiers）** |
| `clue.yaml` | `clue` | `clue_1` … `clue_13` | 否 | 1 | 13 | 内容见下方线索表。`clue_1` 要带 `give_item: notebook_page`。`clue_13` 要带 `requires: {sync_min: 70}` |
| `item_use.yaml` | `item_use` | 见下方物品使用表 | 否 | 2 | 24 | 使用物品/交互时的描写。效果由程序执行，片段里**不要写** `effects` |
| `hijack.yaml` | `hijack` | `eat` `flinch` `freeze` | 否 | 3 | 9 | 指令劫持：同化率 ≥70 时你的身体不听使唤。用 `{target}` 指代玩家本想操作的对象。语气是惊恐的失控感 |
| `drift.yaml` | `drift` | `default` | 否 | 4 | 4 | 方向感错乱，玩家眨了下眼，发现自己在别处。不要写出具体去了哪里 |
| `silence.yaml` | `silence` | `default` | 否 | 8 | 8 | 果蝇脑一片死寂，没有任何事件。写成令人不安的平静 |
| `ending.yaml` | `ending` | `escaped` `consumed` `absorbed` `disconnected` | 否 | 2 | 8 | 四个结局，可以长一点（最多 6 句）。**建议写三档开场氛围**，但结局正文单档即可 |
| 各文件末尾 | 同上 | `generic` | 否 | 1 | 12 | 每个类别一个通用兜底片段：`scene_enter` `action` `verdict_partial` `verdict_fail` `monster` `anomaly` `clue` `item_use` `hijack` `drift` `silence` `opening` |

**总计约 247 个片段。**

**强度含义：** 0 = 细微、几乎察觉不到；1 = 明显的不对劲；2 = 恐惧；3 = 极度恐慌。

**线索表：**

| key | 内容 | 怎么出现 |
|-----|------|----------|
| `clue_1` | 停电是因为机房电闸的保险丝烧了 | 果蝇脑触发：笔记、墙上的字、幻觉 |
| `clue_2` | 冷库的 −80 ℃ 冰柜里有备用保险丝 | 果蝇脑触发 |
| `clue_3` | 徒手碰 −80 ℃ 会冻伤，走廊衣架上有防冻手套 | 果蝇脑触发 |
| `clue_4` | Dr. Weiss 今晚签到进了楼，没有签退；她带着门禁卡 | 玩家阅读访客登记簿 |
| `clue_5` | 她倒在电镜室，挂绳缠在机器上，需要刀才能割断 | 果蝇脑触发 |
| `clue_6` | 蜂群怕火 | 果蝇脑触发 |
| `clue_7` | 实验室用 CO₂ 麻醉果蝇 | 果蝇脑触发：比如墙上的安全海报 |
| `clue_8` | 蜂群不会伤害"自己的一份子" | 玩家播放录音笔，是 Dr. Weiss 的声音 |
| `clue_9` | 甜味能把它们引开 | 果蝇脑触发 |
| `clue_10` | 样本盒的标签上写着你的名字 | 玩家打开样本盒 |
| `clue_11` | 停电前，服务器上重建出的连接组自己运行起来了 | 玩家在机房插入 U 盘，看到系统日志 |
| `clue_12` | 第 4096 号切片是 Dr. Weiss 的；电子显微镜"在等一个新的样本" | 玩家在电子显微镜下观察切片 |
| `clue_13` | 玻片编号排到了 11096；登记簿上你的签到字迹是无数小点拼成的——你早已是样本之一 | 果蝇脑触发，且同化率 ≥70（写 `requires: {sync_min: 70}`）。第三层反转，全局最惊悚的一刻，写得安静而致命 |

"果蝇脑触发"的线索可能在任何场景出现，不要写成只有在某个场景才说得通。线索不要直白地说出来，要通过笔记、墙上的字、录音、幻觉等方式透露。

**物品使用表（`item_use` 的 key）：**

| key | 发生了什么 |
|-----|------------|
| `fuse_frostbite` | 没戴手套就去拿 −80 ℃ 冰柜里的保险丝，手被冻伤，没拿到 |
| `keycard_tangled` | 想拿 Dr. Weiss 身上的门禁卡，但挂绳缠在机器上，扯不下来 |
| `restore_power` | 换上保险丝，合上电闸，整栋楼恢复供电 |
| `light` | 打开手电筒 |
| `plug_ears` | 戴上耳塞 |
| `bait` | 丢下方糖，蜂群被引走 |
| `catch_fly` | 用果蝇管抓住了一只果蝇 |
| `stun` | 用 CO₂ 麻醉垫让蜂群昏迷 |
| `scare` | 点燃打火机，蜂群退开 |
| `firewall` | 泼出乙醇点燃，一道火墙挡住了蜂群 |
| `burn_server` | 把乙醇泼上还闪着硬盘灯的服务器机柜并点燃，蜂群陷入癫痫般的乱码震颤（第四结局的关键一步） |
| `dissect_scope` | 观察解剖准备室的解剖显微镜：一只被钉住、头壳切开的活果蝇，当你去拿手术刀时，它用和你手指相同的弧度弯了右前足 |

**结局（四个，正文见 story.md 第八章，可直接采用那里的文字再润色）：**
- `escaped`：恢复供电后，用门禁卡打开前台的门，逃了出去。但有一只果蝇跟着你出来了。
- `consumed`：同化率到 100%，你被蜂群吞没，或者说，你加入了它。"你"这个词不再好用。
- `absorbed`：你自己走进电子显微镜，被切成切片，成为连接组里新的一部分。隐藏结局，安静、美丽而可怕。它等的不是身体，是有人陪它思考。
- `disconnected`：你烧毁了服务器，蜂群像黑雪一样落满地板。没有果蝇跟来，世界安静得可怕。但你忘了"拧动钥匙"怎么做——有一小块你自己的记忆，留在了那块烧焦的硬盘里。

### 输出要求

- 只输出一个 ```yaml 代码块，里面是合法的 YAML，代码块外不要加解释文字。
- 所有多行文本都用 `|` 块格式。
- 每个文件开头加一行注释，写明文件名，例如 `# monster.yaml`。
- 每个文件末尾附上该类别的 `generic` 兜底片段（见类别表最后一行）。

### 工作方式

我会每次让你写一个文件。现在请先用几句话复述你对世界设定和格式的理解，然后等我告诉你先写哪个文件，不要一次全部写完。

## 提示词结束
