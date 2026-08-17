# Bible AI Studio

把圣经段落变成高质量漫画（最终延伸到 motion comic / anime）的 **AI 视觉叙事编排系统**。

核心不是「圣经文本 → AI 出图」，而是完整管线：

```
Bible Passage → Story Analysis → Screenplay → Character Bible → Location Bible
→ Visual Style Bible → Scene Breakdown → Storyboard → Panels → Page Composition
→ Speech Bubbles → Finished Episode → (future) Motion Comic / Anime
```

**图像模型是可替换的耗材，管线本身才是产品。**

---

## 铁律 HARD RULES — 不可协商

违反下面任何一条都算 bug，不是风格偏好问题。

### 1. 圣经文本神圣不可篡改

- **绝不静默修改圣经原文。** 原文与 AI 改编必须分开存储、分开渲染
- 所有内容必须标注四层之一：
  - `CANONICAL` — 经文直接支持
  - `INFERRED` — 对经文的合理推断
  - `DRAMATIZED` — 为视觉化添加
  - `FICTIONAL` — 无经文支持
- **绝不把编造的对白当作经文引用呈现。** UI 上 `[BIBLE TEXT]` / `[ADAPTED NARRATION]` / `[DRAMATIZED DIALOGUE]` 必须视觉可区分
- 每条 `BiblePassage` 必须记录 `translationId`——不同译本版权条款不同

### 2. 一致性靠固定段强制注入，不靠 LLM 自觉

prompt 必须由结构化片段拼装，**顺序固定**：

```
GLOBAL_STYLE          ← 项目级,所有 episode 共用,永不变
+ CHARACTER_DNA       ← 逐字复用,一个字都不能改
+ LOCATION_DNA        ← 同上
+ SCENE / CAMERA / LIGHTING / ACTION / EMOTION / COMPOSITION   ← 只有这些可变
+ NEGATIVE_PROMPT     ← 含强制排除项
```

- **绝不让 LLM 自由发挥生成完整 prompt。** LLM 只能填「可变」部分，DNA 段由代码注入
- **绝不让每个 panel 自己发明画风。** Style Bible 是项目级的
- 换 checkpoint 会毁掉整集的一致性——同一 episode 内锁定模型

### 3. 内容安全约束（强制注入，非可选）

**Genesis 3 — Adam / Eve（创 3:1–20，穿皮衣 3:21 之前）：**

- 遮挡手法：`long flowing hair` + `foliage / branches / bushes`
- 标注为 `DRAMATIZED`（创 2:25 记载赤身，遮挡是视觉化处理）
- 强制负向标签：`nude, nsfw, exposed`
- 构图偏好：远景 / 背影 / 剪影 / 局部特写（手、脸、果子）

这条在 **prompt 组装层**注入，和 CHARACTER_DNA 同级，不经过 LLM。

### 4. 生成资产只增不减

- **绝不删除历史生成结果。** 重生成 = 新增一条 `GeneratedImage`，不是覆盖
- panel 状态机：`DRAFT → GENERATING → GENERATED → REVIEW → APPROVED / REJECTED → FINAL`
- **发布前必须人工审核**，没有全自动发布路径

### 5. 对白文字绝不烧进 AI 图像

先出干净画面，speech bubble / narration box / SFX 全部作为**可编辑图层**后期叠加。

### 6. Provider 必须可替换

`ImageProvider` / `LLMProvider` / `VoiceProvider` 接口隔离。业务逻辑里**不允许出现任何 provider 专有类型或 URL**。

### 7. AI 产出全部可编辑

任何 AI 生成的字段（角色描述、分镜、prompt、对白）用户都必须能手改，且改动不被下次生成覆盖。

### 8. 阶段间用结构化 JSON

管线每一步的输入输出都是 schema 化 JSON，不是自由文本。

---

## 版权

- **RCUVSS**（和合本修订版·神版·简体）有版权（香港圣经公会）。**仅限 Maverick 自用**，不发布
- 译本文本文件必须 `.gitignore` 排除——避免将来 repo 公开时文本已进 git 历史
- 数据模型保留 `translationId` / `license` / `canRedistribute` 字段
- 英文将来用 NIV（Biblica，同样有版权，同样处理）

---

## 技术栈

Next.js + TypeScript + Tailwind + Prisma + **SQLite**（MVP）+ 本地文件系统存资产。

- 图像：**ComfyUI**（HTTP API，本地/远程同一套代码）
- LLM：走 `LLMProvider` 抽象。本地 8GB 跑不动像样的模型，用 API
- 不做云基础设施，优先本地/开源

---

## 🔒 SD1.5 能力边界（反复验证，不要再浪费时间试）

| 做得好 | 做不到 |
|---|---|
| 单人物、场景、光影氛围 | **道具特写**（七星/钥匙/天平/香炉） |
| 逆光剪影、神圣感 | **精确空间关系**（仆倒、手按肩）— 各试 3 次全败 |
| 统一背景、色彩叙事 | **精确数量**（"七个灯台"试 3 次全败） |
| | **群像** |
| | **神圣人物的面部特写** — 出成红眼恶魔/动漫角色/独眼赛博人 |

**两条设计原则（从失败里学的）：**

1. **不可描绘之物不要拍特写。** 「眼如火焰」「面如烈日」在远景/剪影可以，特写必崩——特写画面必须有主体，模型就会填个怪东西进去。改拍纯光/纯火，让经文旁白承担意义。
2. **精确内容交给文字层。** 七星、利剑、钥匙、数量，全由经文框和图表说明。教学图解体例正好帮了忙：文字承担信息，图只要氛围。

**统一背景是一致性的捷径。** 全篇共用同一片金色云海（`style.unifiedBackground`，自动注入每格）——统一环境比统一角色脸容易得多，视觉统一感却一样强。

## 本地环境（实测，勿凭直觉改）

**硬件：MacBook Pro 2022 / M2 / 8GB 统一内存**——这是硬约束，不是可以忽略的细节。

⚠️ **内存上限 2.5 GB**（Maverick 2026-08-13 定，他有别的东西同时在跑）。
用 `tools/comfy_ctl.sh lowmem`（= `--lowvram --disable-smart-memory`），实测 RSS 0.48 GB ✅，
代价是速度 75 s/格 → **138 s/格**。Maverick 明确说慢没关系。

**SDXL 不可行**：光权重 6.5 GB 就超了。Mac 的"显存"就是内存，`--lowvram` 在 Mac 上帮助有限，
只会疯狂 swap —— 而持续大量 SSD 写入正是最伤机器的那种"慢"。

ComfyUI 装在 `~/ComfyUI`（**repo 外**，模型不进 git）。启停一律用 `tools/comfy_ctl.sh`。

模型：**`dreamshaper_8.safetensors`**（SD1.5 绘画向，古典宗教画用）。
`Counterfeit-V3.0_fix_fp16.safetensors`（anime）保留但已不是默认。

**2026-08-12 实测（512×768 / 20 步）：**

| 配置 | 首次加载 | 热启动 |
|---|---|---|
| `--lowvram --disable-smart-memory` | — | 66–104s（不稳定） |
| `--lowvram` | 319.5s | 75.9s |
| **默认模式（当前采用）** | **92.8s** | **74.2s** |

- ⚠️ `--lowvram` 在这台机器上是**负优化**。2GB fp16 模型本来就装得下，分块加载白增 I/O
- `PYTORCH_ENABLE_MPS_FALLBACK=1` **必需**，不加直接崩
- ⚠️ **768×1152 撞内存墙**（14.1 s/step，是 512×768 的 4 倍）。**实用分辨率上限 = 512×768**
- 一张图 ≈ 74s。一集 60 格 × 5 次重生成 ≈ 6 小时——排期时按这个算

**不用 IPAdapter：** 需常驻 CLIP-ViT-H 2.4GB，而 RAM free 只有 ~3.1GB，必然 swap。LoRA 更适合——推理只加 100–200MB，训练可用 Colab 免费 T4。（一般教程说 IPAdapter 更轻量，那是对 12GB+ 显卡而言。）

---

## 核心数据模型

```
Project ├── Episodes ├── Characters ├── Locations └── Styles
Episode ├── BiblePassages ├── Scenes ├── Panels └── Pages
Character └── CharacterReferences
Location  └── LocationReferences
Scene     └── Panels
Panel     ├── GeneratedImages ├── References └── Dialogues
GenerationJob
```

资产目录结构：

```
project/
├── project.json
├── bible/ characters/ locations/ styles/
├── episodes/ scenes/ panels/ pages/
├── references/ exports/
```

---

## 分镜要求

镜头必须**刻意变化**，不允许连续多格同样的中景。参考节奏：

```
Wide → Medium → Close-up → Reaction → Action → Extreme close-up → Wide payoff
```

预设：extreme wide / wide / full body / medium / medium close-up / close-up /
extreme close-up / over shoulder / low angle / high angle / POV / Dutch angle

---

## 开发阶段

1. **Foundation** — Next.js + Prisma + SQLite + Project/Episode/Character/Location/Style CRUD（先不接 AI）
2. **Story Engine** — 段落分析 → 剧本 → 角色/地点提取 → 分场
3. **Storyboard** — scene/panel 编辑器 + 镜头预设 + prompt 生成
4. **ComfyUI** — 连接 + workflow + 队列 + 存图 + 重生成 + 审批
5. **Manga Composer** — 页面布局 + 气泡 + 旁白 + SFX + PNG/PDF 导出
6. **Consistency** — 角色参考图 + ControlNet + LoRA + inpainting
7. **Anime**（暂不实现）

**每个阶段结束后应用必须可运行。不要过度设计 MVP。**

第一集测试顺序：`Genesis 1 创世` → `Genesis 3 堕落`（测 Adam/Eve/蛇一致性）→ `David & Goliath`（测动作/群众/尺度）

---

## 决策日志

| 日期 | 决定 | 理由 |
|---|---|---|
| 2026-08-12 | 受众：仅 Maverick 自用 | 解除译本版权顾虑；画质要求可妥协 |
| 2026-08-12 | 中文优先，译本 RCUVSS | 英文 NIV 后续 |
| 2026-08-12 | 画风：anime | 让 M2/8GB 本地方案从「妥协」变「最优解」——SD1.5 anime 生态成熟，且 anime 角色特征符号化，一致性比写实好做一个量级 |
| 2026-08-12 | 预算 $0，全本地 | 不租云 GPU、不用托管 API |
| 2026-08-12 | 一致性 spike 提到 Phase 1 之前 | 原 spec 把 ControlNet/LoRA 放 Phase 6，顺序反了——一致性做不到的话前面全白做 |
| 2026-08-12 | 不训 LoRA、不用 IPAdapter，纯 prompt | Maverick 决定。8GB 上 IPAdapter 代价过高；LoRA 需先有一致图作训练素材 |
| 2026-08-12 | Genesis 3 用长发+植被遮挡 | Maverick 拍板 |
| 2026-08-13 | **体例改为教学式经文图解** | Maverick 提供 4 张样张（`sample/`）作为目标。逐节经文直引 + 色带章节标题 + 编号小节 + 概要表 + 核心真理 + 金句卷轴 + 页码。不再做纯叙事漫画 |
| 2026-08-13 | **画风改为古典宗教绘画** | 弃 anime。checkpoint `Counterfeit-V3.0` → `dreamshaper_8` |
| 2026-08-13 | 采用统一金色云海背景 | 样张验证过的一致性捷径，比锁角色脸容易得多 |
| 2026-08-13 | 内存上限 2.5 GB | Maverick 有别的东西在跑。用 `comfy_ctl.sh lowmem`，接受 138 s/格 |
| 2026-08-13 | 全本地，不用商业 API | Maverick「我想你全做」。靠改设计绕开模型短板，不靠混合方案 |

---

## 沟通

Maverick 英文不强，**默认用中文回复**。代码、路径、标识符、错误码保持英文。

**绝不静默失败**——被卡住、有歧义、有不确定就立刻明说，不要猜、不要绕过、不要用局部成功掩盖失败。
