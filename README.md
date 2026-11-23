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

## 提供物（三形态，一个真相源）

`character.json` 是唯一真相源；sqlite3 / pg.sql 是**确定性派生产物**（同 JSON → 同字节），
由 `scripts/build_artifacts.py` 从 JSON 派生。三形态不是三份真相源——这是多形态分发最容易
踩的坑，生成器 + MANIFEST 的 sha256 一致性就是防漂移机制。

| 产物 | 形态 | 消费者 | 用途 |
|---|---|---|---|
| `dist/character.json` | 20 字段中性 JSON | fate / qiming | 真相源；直接比对、契约校验 |
| `dist/character.sqlite3` | 20 列中性表 + char 唯一索引 | fate（CE）| 本地/离线装载，替代 dbinit 重建 |
| `dist/character.pg.sql` | PG DDL + INSERT | qiming（EE）| PG 初始化灌入字库表 |
| `dist/MANIFEST.json` | sha256 + 行数 | 双方 | 校验三产物未漂移 |

**为何中性 20 字段而非某家的 ent schema**：fate 是 25 字段、qiming 是 23 字段，
两者不同；20 字段是共同交集（含 fate required 的 `radical_stroke`/`science_stroke`）。
各家把中性表映射到自己的 ent schema（qiming 的 EE 字段由 ent 默认值补齐）。

```bash
python3 scripts/build_artifacts.py --source <canonical.json>   # 生成三产物
python3 scripts/build_artifacts.py --self-test                 # 确定性/漂移检测反例
```

产物在 `dist/`（已 gitignore），通过 GitHub Releases 分发，不进 git 历史。

## 数据生产脚本（2026-11-23 从 fate 迁入）

fate 原 `data/download/*.py`（3 个幂等下载脚本）与来源文档已物理迁入本仓 `data/`。
fate 侧删除后，其门禁 `arch: no data-production scripts in CE repo` 断言已启用并全绿——
数据生产职责在架构层强制归位，不再依赖人工约定。

数据生产链路：外部源 → `data/download/*.py` → `character.json` → `build_artifacts.py` → 三形态产物。
详见 `data/README.md`。

## 状态

- 契约校验器 + 三形态生成器 + 幂等下载脚本均已就位并通过验收。
- fate 侧数据脚本已清空，架构门禁在结构层强制数据流方向。
- 待接入：正式源（qiming.db / export-ce）未在本机，当前用 fate 现有 30060 条数据验证链路。
- export-ce 字段差异已通过 pg.sql 列裁剪解决（只灌 qiming ent 能接的 16 个标量列，
  排除 fate 专有的 `radical_stroke`/`science_stroke` 与 edge 列），详见 qiming 私有仓设计文档。
