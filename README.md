# datasources

开源字库数据的**生产与契约仓**。为 fate（CE）与 qiming（EE）供给 `character.json`。

## 职责边界

- 本仓为 PUBLIC / MIT，只承载**开源字库数据**。
- qiming 的 EE 富化字段（`common_level` / `gender_hint` / `has_poetry` / `is_ancient`）与付费数据模块**不进本仓**，留在 qiming 私有仓。
- 本仓不产出代码依赖：fate / qiming 通过数据产物（而非 import）消费，fate 保持独立 clone/build。

## 数据契约（唯一真相源：消费端）

`entity/ent/schema/character.go` 的字段集与 fate 消费端 `resources/character.json` 的 20 字段**扁平快照**对齐，不是 fate 的内部存储 schema（后者含边关系与 EE 字段）。

任何产物必须过 `scripts/verify_dataset.py`：

| 规则 | 判据 |
|---|---|
| 条数 | 30060 |
| 必填 | `char` `unicode` `wu_xing` `radical` `radical_stroke` `simplified_stroke` `traditional_stroke` `science_stroke` `source` |
| 稀疏 | `kangxi_stroke` `pinyin` 及布尔标志（允许缺失/null） |
| 类型 | 每字段运行时类型固定；`bool` 与 `int` 严格区分 |
| 不变量 | `char` 唯一且非空；`unicode` 为 `U+XXXX`；`wu_xing` ∈ {木,火,水,金,土}；`pinyin` 元素为字符串 |

```bash
python3 scripts/verify_dataset.py           # 校验 dist/character.json
python3 scripts/verify_dataset.py --self-test # 检测器必中反例
```

fate 侧用**同一份脚本**校验其 embed 数据，保证两端判定一致。

## 提供物（一个契约 + 一个灌库脚本）

**上位规则见 `docs/ARCH_CONTRACT.md`。** 数据库的方言文件（sqlite / pg dump）是运行时产物，
不是数据契约，本仓不分发数据库文件。

`character.json` 是唯一数据契约；`character.pg.sql` 是给 qiming PG 运行时的**便利灌库脚本**
（从 JSON 确定性派生、幂等），不是第二份契约，fate 不消费它。
fate 通过 embed `character.json` + `cmd/dbinit` 自行生成其运行时 sqlite（见 fate 仓）。

| 产物 | 形态 | 消费者 | 用途 |
|---|---|---|---|
| `dist/character.json` | 20 字段中性 JSON | fate / qiming | **唯一数据契约**；比对、校验、embed |
| `dist/character.pg.sql` | PG DDL + 幂等 INSERT | qiming（EE）| PG 初始化灌库脚本（派生，非契约） |
| `dist/MANIFEST.json` | sha256 + 行数 | 双方 | 校验产物未漂移 |

> 曾有 `character.sqlite3` 作为"供 fate 装载"的第三形态，已删除：fate 用 embed + dbinit，
> 从不读取它，属于重复且无人消费的死产物。

**为何中性 20 字段而非某家的 ent schema**：fate 是 25 字段、qiming 是 23 字段，
两者不同；20 字段是共同交集（含 fate required 的 `radical_stroke`/`science_stroke`）。
各家把中性契约映射到自己的 ent schema（qiming 的 EE 字段由 ent 默认值补齐）。

```bash
python3 scripts/build_artifacts.py --source <canonical.json>   # 生成契约 + 灌库脚本
python3 scripts/build_artifacts.py --self-test                 # 确定性/漂移/无数据库文件反例
```

产物在 `dist/`（已 gitignore），通过 GitHub Releases 分发，不进 git 历史。

## 数据生产脚本（2026-11-23 从 fate 迁入）

fate 原 `data/download/*.py`（3 个幂等下载脚本）与来源文档已物理迁入本仓 `data/`。
fate 侧删除后，其门禁 `arch: no data-production scripts in CE repo` 断言已启用并全绿——
数据生产职责在架构层强制归位，不再依赖人工约定。

数据生产链路：外部源 → `data/download/*.py` → `character.json`（契约）→ `build_artifacts.py` → pg 灌库脚本。
详见 `data/README.md`。

## 状态

- 契约校验器 + 生成器（契约 + PG 灌库脚本）+ 幂等下载脚本均已就位并通过验收。
- fate 侧数据脚本已清空，架构门禁在结构层强制数据流方向。
- 2026-11-23 纠正：删除 `character.sqlite3` 死产物（无人消费），职责契约固化于 `docs/ARCH_CONTRACT.md`。
- 待接入：正式源（qiming.db / export-ce）未在本机，当前用 fate 现有 30060 条数据验证链路。
- export-ce 字段差异已通过 pg.sql 列裁剪解决（只灌 qiming ent 能接的 16 个标量列，
  排除 fate 专有的 `radical_stroke`/`science_stroke` 与 edge 列），详见 qiming 私有仓设计文档。
