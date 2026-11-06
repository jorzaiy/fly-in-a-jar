---
inclusion: fileMatch
fileMatchPattern: ["content/**/*.yaml", "app/content/**/*.py", "app/narrator/**/*.py"]
---

# 片段库与内容约定

处理 `content/` 下的 YAML、内容加载器或叙事模块时适用。完整写作指南（也是给 Gemini 的提示词）在 `.kiro/specs/fly-brain-horror/fragment-guide.md`。

## 片段格式要点

- 每个文件是 YAML 列表；每个片段必填 `id`、`category`、`key`，以及 `zh` + `en`，或者 `tiers`（human / latent / instinct，至少有 human）。
- `id` 格式：`<category>_<key>_<两位序号>`，只用小写字母、数字、下划线，全局唯一。
- 只有 `monster` 和 `anomaly` 按强度（`intensity: 0–3`）；其他类别不写 intensity。
- `tiers` 只允许用在 opening、scene_enter、anomaly、ending。
- 占位符只有 `{target}`，只能用在 action、verdict_fail、hijack。
- `effects.sync` 范围 −5 到 +12；`item_use` 片段不能带 effects（规则引擎负责效果）。
- `clue_13` 必须 `requires: {sync_min: 70}`；`clue_1` 应 `give_item: notebook_page`。
- 每个类别（ending 除外）都要有一个 `key: generic` 的兜底片段。
- 中文不超过 100 字，英文不超过 60 个单词（ending 除外）。

## 文风

第二人称、现在时；心理恐怖，不写血腥；中英各自是好文字。不替玩家做决定，不在文字里给物品、移动玩家或结束游戏（除非 effects 里写了）。

## 覆盖目标

- **底线：** 每个 key 至少 1 个片段（测试强制）。
- **MVP：** 每个"类别 × 强度档"格子至少 2 个非 generic 片段。monster、anomaly 各有 4 个强度档，其余类别各算 1 格。`python -m content.validate` 末尾打印 MVP 汇总；`--mvp` 时未达标返回非零。
- **完整（stretch）：** fragment-guide.md 类别表里的数量，约 247 个。

## 改内容后的检查

1. `python -m content.validate` 必须 0 errors（hook 会在保存时自动跑）。
2. 占位片段是为了让游戏先跑通，正式文本来自用户的 Gemini 写作。**不要自己编写正式片段**，除非用户明确要求；内容问题先问用户。
3. 新增类别、key 或物品规则时，同步改 `app/content/schema.py`、`content/world.yaml` 和 fragment-guide.md。
