# Kiroween 2026 规则核实

核实日期：2026-11-05。来源只认 Devpost 官方页面：

- 正式规则：https://kiroween.devpost.com/rules
- 概览页：https://kiroween.devpost.com/

如果规则和概览页有出入，以正式规则为准（规则第 11 节）。规则在提交期内仍可能修改，提交前再看一眼 Updates 页：https://kiroween.devpost.com/updates

## 时间

| 事项 | 时间（太平洋时间） |
|------|--------------------|
| 提交期 | 2026-10-30 09:00 – 2026-12-04 14:00 |
| 评审期 | 2026-12-16 13:00 – 2027-01-29 13:00 |
| 公布结果 | 约 2027-02-03 09:00 |
| Kiro 免费额度申请截止 | 2026-12-01 12:00（一次性 4000 credits） |

**只收新项目：** 项目必须在提交期内（10-30 之后）新建。可以用框架、库和模板，但其他已有代码或作品必须在提交时说明。本仓库第一个提交是 2026-11-01，符合要求。

## 我们选的类别：Frankenstein

原文：*"Stitch together a chimera of technologies into one app. Bring together seemingly incompatible elements to build something unexpectedly powerful."*

本项目缝合的三样东西：真实果蝇连接组的 LIF 模拟（FlyWire v783）、Jev 结构化决策模型（只判定不写字）、预写的双语片段库。三者原本互不相干，拼在一起成了一个由果蝇脑讲故事的游戏，正好对上这个类别。

其他三个类别：Resurrection（复活过时技术）、Skeleton Crew（骨架模板 + 两个应用）、Costume Contest（恐怖风格的精致界面）。

## 必须做到的提交要求

1. **用 Kiro 构建：** 用 Kiro（IDE、CLI、Web 或 Kiro Crew）做出可运行的软件。Kiro 用得不够，评委可以直接取消资格。
2. **应用链接：** 提供可用的应用 URL。需要登录的话，把账号和说明写在提交表单里（只有评委能看到）。
3. **文字介绍：** 说明项目的功能。
4. **演示视频：**
   - 应少于 3 分钟，评委不必看 3 分钟以后的部分；
   - 要拍到项目在目标设备上实际运行；
   - 必须上传到 YouTube 并设为公开，把链接填进表单；
   - 不得包含第三方商标、受版权保护的音乐或其他素材，除非已获许可。
5. **GitHub 仓库：** 公开的 GitHub 仓库（不能是 GitLab 或 Bitbucket）。
   - 包含让项目能运行的全部源码、素材和说明；
   - 必须开源，带开源许可证文件，并且许可证要能在仓库首页的 About 栏里被识别出来；
   - 仓库**根目录**必须有 `/.kiro` 目录，用来展示 Kiro 的使用情况，例如 specs、hooks 和 steering；
   - **不得**把 `/.kiro` 或它的子目录写进 `.gitignore`，否则可能被取消资格。
6. **注明类别和附加奖项。**
7. **Kiro 使用说明（必填）：** 让评委看懂你如何有效地使用了 Kiro。规则举的方向：
   - 用了 Kiro IDE、CLI、Web、Crew 中的哪些，有什么区别；
   - 自定义 agent；
   - Agent hooks：自动化了哪些流程，对开发有什么帮助；
   - Spec 驱动开发：spec 怎么组织，和 vibe coding 相比怎样；
   - Steering：怎么用 steering 改进 Kiro 的回答，哪种策略最有效；
   - MCP；
   - 基于属性的测试（PBT）；
   - Kiro powers。
8. **语言：** 所有提交材料用英文，或者附英文翻译（视频、文字介绍、测试说明等）。
9. **第三方：** 用到的第三方 SDK、API 和数据必须按其条款获得授权（对应 FlyWire 数据许可和 Jev API 条款）。
10. **免费可测：** 评审期结束前，评委必须能免费、无限制地使用项目。

## 评审标准

第一轮：通过/不通过，看项目是否切题、是否合理使用了 Kiro。

第二轮：五项各占 20%（各 10 分）：

| 标准 | 评委看什么 |
|------|------------|
| Potential Impact | 是否为真实受众解决真实问题，是否好用、易上手 |
| Technological Implementation | Kiro 用得是否深入、熟练；AI 开发是否有策略；是否用了多种 Kiro 工具；是否有实验 |
| Design | 是完整、连贯的产品体验，而不只是技术演示；设计是否直观、精致、有意图 |
| Innovation/Idea | 概念是否新颖；是否以独特方式结合了少见的技术或公开资源（如数据集） |
| Presentation | 视频是否完整演示端到端流程；是否讲清楚解决什么问题、给谁用、为什么重要；是否有创意、令人难忘 |

与本项目相关的附加奖：Best Demo（不需额外操作）、Bonus Blog（发公开博客并注明为 Kiroween 2026 而写）、Social Blitz（帖子必须以 `#KiroweenHackathon26` 开头）。

## 和旧版 requirements.md 的差异

| 条目 | 旧写法 | 2026 规则 |
|------|--------|-----------|
| 10.1 | 公开 GitHub 仓库 + 开源许可证 | 同上，另外许可证要能在仓库 About 栏被识别；不能用 GitLab/Bitbucket |
| 10.2 | `.kiro`（spec 和 steering），不进 gitignore（标注"2025 年规则，待核实"） | `/.kiro` 放在仓库根目录，展示 specs、**hooks** 和 steering；目录及子目录都不能进 gitignore |
| 10.4 | 3 分钟以内（标注"时长待核实"） | 一致：少于 3 分钟；新增：公开上传 YouTube、拍到实际运行、不用无授权的音乐和素材 |
| 新增 | — | 必须附 Kiro 使用说明；材料用英文；只收提交期内新建的项目；提供可用的应用 URL |
