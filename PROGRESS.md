# 进度 — 2026-08-13

## 现状一句话

**方向发生了两次重大转向**：画风 anime → 古典宗教绘画，体例 叙事漫画 → 教学式经文图解。
排版器和页面结构已写完，**但 v5 的图一张都还没生成**。

可看的成品仍是旧版：`exports/rev-01.pdf`（anime 风、叙事漫画体例、24 格 / 6 页）。

---

## 今天的两次转向

### 转向一：体例 —— 叙事漫画 → 教学式经文图解

Maverick 上传了 4 张 ChatGPT 生成的样张（`sample/`）作为目标参照。分析后发现那是**另一种体例**：

| | 样张（目标） | 我之前做的 |
|---|---|---|
| 文本 | **逐节经文直引 + 出处标注** `(启示录 6:2)` | 选段改编旁白 |
| 结构 | 色带章节标题、编号小节、概要表、核心真理、我们的回应、结语、页码 | 纯分镜叙事 |
| 一致性策略 | **统一背景**（金色云海贯穿全篇） | 锁角色 seed |

**关键判断**：样张的优秀一半来自排版（我能 100% 复制），一半来自模型能力（SD1.5 复制不了）。所以策略是**把排版层做到位，图只承担氛围与主体**。

### 转向二：画风 —— anime → 古典宗教绘画

- checkpoint：`Counterfeit-V3.0`（纯 anime）→ **`dreamshaper_8.safetensors`**（绘画向，2.0 GB，已下载）
- 画风 DNA 改为 `(classical religious oil painting:1.3), (renaissance sacred art:1.2)` 等
- 负向新增 `anime, manga, cel shading, flat colors, chibi`
- **新增统一背景**：`(sea of luminous golden clouds:1.2)` 自动注入每一格

**画风测试结果（4 格实测）**：

| 格 | 结果 |
|---|---|
| 约翰全身 | ✅ 很好，接近样张质感 |
| 人子全身 | ✅ 好，逆光巨影 + 金云 |
| 手托七星 | ❌ 抽象星芒，没有手 |
| 俯角仆倒 | ❌ 模糊人脸浮在雾里 |

---

## 🔒 SD1.5 的能力边界（反复验证过，不要再试）

| 做得好 | 做不到 |
|---|---|
| 单人物、场景、光影氛围 | **道具特写**（七星/钥匙/天平/香炉） |
| 逆光剪影、神圣感 | **精确空间关系**（仆倒、手按肩）—— 各试 3 次全失败 |
| 统一背景、色彩叙事 | **精确数量**（"七个灯台"试 3 次全失败） |
| | **群像**（未测，但必崩） |
| | **神圣人物的面部特写** —— 试 3 次分别出成红眼恶魔/动漫角色/独眼赛博人 |

### 两条从失败里学到的设计原则

1. **不可描绘之物不要拍特写。** 「眼如火焰」「面如烈日」在远景/剪影可以，特写必崩——特写画面必须有主体，模型就会填个怪东西进去。改拍纯光/纯火，让旁白经文承担意义。
2. **精确内容交给文字层。** 七星、利剑、钥匙、数量，全部由经文框和图表说明，不强求画出来。教学图解体例正好帮了忙——文字承担信息，图只要氛围。

---

## ✅ 已完成（代码 / 数据）

```
CLAUDE.md                              铁律 + 实测数据 + 决策日志
PROGRESS.md                            本文件
.gitignore
sample/                                Maverick 提供的 4 张目标样张
data/bible/cuv/rev-1.json              启示录 1 章(和合本,公共领域)
data/episodes/rev-01.json              角色/地点/画风 Bible(已改古典画风 + 统一背景)
data/episodes/rev-01-storyboard.json   v5 教学版 17 格(只用 SD1.5 擅长的画面类型)
data/episodes/rev-01-pages.json        ★ 新增 —— 教学图解版面结构(5 页)
data/episodes/rev-01-generated.json    生成记录(逐格落盘,含 history)
exports/rev-01.pdf                     旧版成品(anime/叙事体例)
tools/fetch_bible.py                   经文抓取(只允许公共领域译本)
tools/workflows.py                     prompt 拼装 + 景别系统 + workflow 构造
tools/generate_episode.py              storyboard → panel 图
tools/compose_pages.py                 旧版叙事漫画排版
tools/compose_teaching.py              ★ 新增 —— 教学图解排版(未跑过)
tools/composite_lampstands.py          ★ 新增 —— 七灯台程序化合成(未跑过)
tools/comfy_client.py                  ComfyUI 客户端 + 硬件保护
tools/openpose_gen.py                  程序化骨架(ControlNet 用,当前未启用)
tools/comfy_ctl.sh                     启停控制 + 低内存模式 + 内存查询
```

### 新增的排版能力（`compose_teaching.py`，7 种块）

`header` 页眉 / `band` 色带章节标题 / `row` 图格(编号+小标题+经文框+出处) /
`table` 概要表 / `truths` 核心真理 / `quote` 金句卷轴 / `footer` 结语条 —— 外加页码。

版面由 `rev-01-pages.json` 驱动，5 页结构已写好（含"人子的九项形象"表、"核心真理"4 条、金句卷轴、结语）。

---

## ⏸ 没做完的

- [ ] **v5 的 17 格图一张都没生成**（被中断在第一格之前）
- [ ] `compose_teaching.py` **从未跑过**，可能有 bug
- [ ] `composite_lampstands.py` **从未跑过**
- [ ] 启示录第 2 章

### 继续时的命令

```bash
tools/comfy_ctl.sh lowmem                                  # 低内存模式启动
python tools/generate_episode.py rev-01 --steps 26 --variant 2   # 17 格,约 40 分钟
python tools/compose_teaching.py rev-01                    # 出教学版 PDF
```

---

## 环境约束（重要）

- **内存上限 2.5 GB**（Maverick 2026-08-13 定，他有别的东西在跑）
  - 用 `tools/comfy_ctl.sh lowmem` = `--lowvram --disable-smart-memory`
  - 实测生成后 RSS 0.48 GB，远低于上限 ✅
  - 代价：速度从 ~75 s/格 降到 **~138 s/格**。Maverick 明确说慢没关系
- **SDXL 不可行**：光权重 6.5 GB 就超了。Mac 的"显存"就是内存，`--lowvram` 在 Mac 上帮助有限，只会疯狂 swap——而持续大量 SSD 写入正是最伤机器的
- 跑长任务前 `caffeinate -dimsu`，结束后务必 kill 掉
  - ⚠️ 系统里还有别的 `caffeinate -i` 进程属于其他工具，**不要误杀**

## 修掉的 bug

- `comfy_ctl.sh` 的 `pkill -f "ComfyUI/main.py"` **从来没匹配上过** —— `start.sh` 是 `cd` 之后跑 `./venv/bin/python main.py`，命令行里没有那个路径串。以前每次"停止"都是超时后靠 lsof 强杀。已改成用端口定位进程
- `generate_episode.py` 的 manifest 改成**逐格落盘**，中断不再丢记录；另加 `--rebuild-manifest` 可从磁盘图片重建
- macOS python.org Python 的 SSL 证书问题（跑了 `Install Certificates.command`）

## 待 Maverick 决定

- **混合方案要不要做**：模型做不到的三类（神圣人物面部、精确道具、群像）用 ChatGPT 出图，其余本地跑。Maverick 上次说"我想你全做"，所以当前按全本地推进，靠改设计绕开短板
- **RCUVSS 文本**：有版权，需自行导入。当前用和合本 1919（CUV，公共领域）顶替，`translationId` 已标注，换字段即可切换
