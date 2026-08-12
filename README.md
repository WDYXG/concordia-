# Riverbend Concordia Agent World

这是一个基于官方 Concordia 构件的轻量级生成式社会模拟项目。Riverbend
小镇选举现在既保留了原来的单次投票实验，也具备一个可复用的多轮 Agent
世界框架和浏览器可视化。

当前版本为 **V1.0.0 研究原型**。它用于演示和研究 LLM Agent 在受控小世界中的
信息传播、行动和投票过程，不用于预测真实人类、真实选举或真实政策效果。本项目
独立开发，不是 Google 或 Google DeepMind 的官方项目。

## 快速开始

需要 Python 3.12。以下命令不会调用任何付费 API：

```powershell
git clone https://github.com/WDYXG/concordia-.git
cd concordia-
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

测试通过后，可以直接打开 `web\riverbend_world.html` 查看内置演示。该页面在本地
运行，不需要 API Key；也可以导入本机生成的 `outputs\world_runs\*.json` 文件。

如需运行 DeepSeek 实验：

```powershell
Copy-Item .env.example .env
```

然后只在本机 `.env` 中填写 `DEEPSEEK_API_KEY`。`.env` 已被 Git 忽略，不要在
Issue、日志、截图或提交中公开密钥。真实 API 命令必须显式提供
`--confirm-live-api`，以避免误产生费用。

## 当前能力

- 5 个具有身份、目标、位置和初始记忆的 Agent。
- 6 个小镇地点和确定性的 `WorldState`。
- 多轮“观察、回忆、提议动作、GM 验证、状态更新、下一轮反馈”循环。
- LLM Agent 的下一轮 Prompt 包含上一动作的 GM 接受/拒绝结果及原因。
- `move`、`speak`、`inspect`、`vote` 四种 Skill。
- 基于 Agent、角色、参数和世界规则的权限验证。
- 情景记忆、神经语义检索、社会消息和来源追踪。
- 公开信息、私聊隔离、转述来源和关系变化。
- 四组实验、固定种子、条件顺序随机化、Agent 顺序随机化和候选人顺序平衡。
- 操纵检查、动作统计、投票统计、关系与记忆统计。
- 正式 Live 选举从投票地点开始，并单独报告有效选票与未投票人数。
- 候选人顺序可按 seed 自动交替，公告正文和 metadata 使用同一顺序。
- DeepSeek 多轮控制器、完整 Prompt/响应轨迹和 token 用量记录。
- 本地 FastEmbed + ONNX 多语言语义模型；运行时不联网。
- 一个可播放、暂停、单步和切换实验条件的网页小世界。

## 项目结构

```text
concordia_riverbend/
├── core/             通用场景、世界状态、多轮引擎、Skill 和权限
├── agents/           单次 Voter Agent 和多轮 LLM Agent 控制器
├── game_master/      原选举 GM 和确定性选票账本
├── memory/           本地嵌入、事件记忆和社会记忆
├── language_models/  DeepSeek 与 Concordia 的接口适配
├── scenarios/        Riverbend 人物、地点、动作和实验条件
└── experiments/      原投票实验、多轮实验计划和统计

scripts/              检查、生成、运行和网页构建命令
web/                  TypeScript 小世界网页和演示数据
legacy/               第一版非 Concordia 独立原型
```

更详细的技术线路见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 无 API 查看网页

当前工作目录应为项目根目录。

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_world_demo
cd web
bun run build
cd ..
.\.venv\Scripts\python.exe -m scripts.build_world_html
```

然后打开：

```text
web\riverbend_world.html
```

网页内嵌的是确定性脚本实验，不会调用 DeepSeek。它用于验证框架、世界状态和
可视化流程，不是 LLM 研究结果，也不能代表真实人类行为。

### 导入真实 API 实验结果

打开 `web\riverbend_world.html` 后，点击右上角的“导入结果”，可以一次选择
一个或多个 `outputs\world_runs\*.json`。网页会把每个文件作为一个可切换的
实验运行，并展示：

- 逐轮 Agent 位置、动作和世界事件。
- GM 对动作的接受或拒绝判定及原因。
- 每轮发送给模型的 Prompt、原始响应和解析动作。
- 模型名称、实验 seed、API 请求数和 token 用量。
- 各运行的有效动作、最终选票和候选人票数。

导入过程使用浏览器的本地文件读取能力，不会上传文件，也不会再次调用
DeepSeek。刷新页面或点击“演示数据”即可回到内置脚本演示。

## 无 API 检查世界

```powershell
.\.venv\Scripts\python.exe -m scripts.describe_world
```

输出完整 JSON：

```powershell
.\.venv\Scripts\python.exe -m scripts.describe_world --json
```

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

测试和网页演示都使用假模型或脚本控制器，不会调用 DeepSeek。

## 真实多轮 DeepSeek 世界

以下命令会产生 API 费用，因此必须显式增加确认参数：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_live_world `
  --condition baseline `
  --life-days 10 `
  --candidate-order auto `
  --memory-backend semantic `
  --confirm-live-api
```

默认协议包含 10 个生活日和第 11 天选举，每天 5 个 Agent 各决策一次，
因此至少需要 55 次模型请求；若 JSON 格式无效并重试，最多约 110 次。
未提供 `--confirm-live-api` 时，程序会在创建模型客户端之前退出，不会调用
API。

生活阶段每天从本地事件池按 seed 广播一个随机事件，Agent 可以移动、交流
或调查，但 GM 会拒绝提前投票。第 10 天广播该运行所属实验组的信息处理；
第 11 天所有 Agent 进入 `town_hall`，此时只允许投票或等待。同一 seed 在
四个条件中使用完全相同的背景事件日程。

投票动作在同一次模型回答中保存候选人和一至两句第一人称理由，不需要额外
的理由生成请求。网页“投票”页签会集中显示五位 Agent 的选择与理由；早期
未保存理由的 JSON 仍可导入，并会明确标注理由缺失。

## 四组 Live 批量实验

先用 `--validate-only` 核对现有基线与计划，不会调用 API：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_four_condition_world `
  --baseline-run outputs\world_runs\20260729T135903_816624Z.json `
  --seed 20260729 `
  --candidate-order bob-first `
  --life-days 10 `
  --memory-backend semantic `
  --validate-only
```

确认后将 `--validate-only` 替换为 `--confirm-live-api`。脚本复用基线，
只运行 placebo、employment evidence 和 pollution evidence 三组，预计
额外产生 165–330 次模型请求。每完成一组都会更新
`outputs\world_batches\` 下的进度清单；失败时停止且保留已完成结果。

`--candidate-order auto` 根据 seed 奇偶稳定交替候选人顺序；例如连续使用
`20260727` 和 `20260728` 时，分别得到 Alice-first 和 Bob-first。正式比较
每个信息条件时，应为同一条件至少运行一对奇偶 seed，不能用一次运行声称
已经完成条件内顺序平衡。

`semantic` 是默认记忆后端，使用项目内已下载的多语言 ONNX 模型。若需要
完全不加载神经模型，可显式使用 `--memory-backend hash`。

## 本地语义记忆

模型下载到 `models\fastembed\`，真实运行只读取本地文件。重新下载：

```powershell
.\.venv\Scripts\python.exe -m scripts.download_semantic_model
```

比较 Hash 与神经语义检索：

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_semantic_memory
```

当前六个同义和中英文跨语言检索样例中，Hash Top-1 为 3/6，神经模型为
6/6。这个小测试用于确认接线和基本语义能力，不是通用检索基准。

结果保存到 `outputs\world_runs\`，包括：

- 完整场景、轮次和每次状态快照。
- Agent 的观察、回忆和动作结果。
- 控制器 Prompt、原始响应和解析错误。
- 模型、随机种子、Agent 顺序和候选人顺序。
- provider 返回的 prompt、completion 和 total token。
- `ballots_cast`、`unvoted_count` 和未投票 Agent ID。

程序不假设价格。成本应根据运行日期和实际模型价格另行计算。

## 原有实验

单次五选民投票：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_five_voter_election
```

四组确定性 Game Master 实验：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_condition_experiment `
  --runs-per-condition 1
```

V1 以 `scripts\` 中的模块化运行入口为准。

## 研究边界

- 重复运行使用相同的合成 Persona，不能当作独立人类受试者。
- FastEmbed 模型能处理同义表达和中英文跨语言检索，但仍可能在否定、讽刺、
  长上下文或专业术语上出错。
- HashingTextEmbedder 继续作为无需模型文件的确定性降级后端。
- 网页脚本投票是固定演示结果，不能用于报告实验效应。
- 正式结论需要预注册设计、足够运行次数、操纵检查和跨模型稳健性分析。

## 与 Concordia 的关系

本项目通过 PyPI 依赖 `gdm-concordia==2.4.0`，并在 Agent、Game Master、环境引擎
和语言模型接口中调用其公开构件；仓库不复制官方 Concordia 源码。有关框架设计，
请参阅 [Google DeepMind Concordia](https://github.com/google-deepmind/concordia)。

使用本项目开展研究时，也请引用 Concordia 论文：

```bibtex
@article{vezhnevets2023generative,
  title={Generative agent-based modeling with actions grounded in physical,
         social, or digital space using Concordia},
  author={Vezhnevets, Alexander Sasha and others},
  journal={arXiv preprint arXiv:2312.03664},
  year={2023}
}
```

## 许可证

本项目以 [Apache License 2.0](LICENSE) 发布。第三方依赖仍适用各自的许可证。
V1 的功能清单见 [CHANGELOG.md](CHANGELOG.md)。
