# 职责契约（上位规则 · 三仓唯一真相源）

本文件定义 fate / qiming / datasources 三仓的职责边界与数据流方向。
任何实现、README、部署脚本与本文件冲突时，以本文件为准；改动本文件需三仓同步。

## 三个概念（不得混用）

| 概念 | 定义 | 归属 | 生命周期 |
|---|---|---|---|
| 数据源 (data source) | 原始外部数据（Unihan / 新华字典 / 诗词等） | datasources 独占 | 拉取/清洗脚本 |
| 数据契约 (data contract) | `character.json`，20 字段中性真相源 | datasources 独占产出 | 版本化、可 sha256 校验 |
| 运行时数据库 (runtime DB) | 应用按自身 schema 把契约灌入的可查询库 | fate / qiming 各自独占 | 每次 clone/build 时生成，不入库 |

**SQLite / PostgreSQL 是运行时数据库的方言，不是数据契约。**
禁止把任何数据库文件（`*.db` / `*.sqlite3` / `*.sql` dump）当作跨仓分发的"数据产物"。

## 职责边界（写死，非分叉）

| 仓 | 做 | 不做 |
|---|---|---|
| datasources | 拉取外部源 → 清洗 → 产出并校验 `character.json`；产出 qiming 专用的 PG **灌库脚本**作为便利派生（非契约） | 不持有运行时 DB；不决定 fate/qiming 的 schema |
| fate (CE) | embed `character.json`；`cmd/dbinit` 从 embed 生成 `fate` 运行时库 | 不做数据拉取/清洗；不消费 datasources 的 sqlite |
| qiming (EE) | 消费 `character.json` 或 PG 灌库脚本；自有付费表与 EE 增强字段 | 不重做字库数据处理；运行时库方言由部署形态决定 |

## 数据流方向（唯一）

```
外部源 ──(datasources 拉取+清洗)──> character.json [唯一契约]
                                      │
                    ┌─────────────────┴──────────────────┐
                    ▼                                    ▼
        fate embed + dbinit                    qiming 灌库脚本 / embed
        → 运行时 sqlite (fate)                 → 运行时 PG (容器) 或 sqlite (本地)
```

- 数据流向：**datasources → fate / qiming**，单向。
- 代码依赖方向：**qiming → fate (public API)**，单向。
- 两者正交，不得混淆（曾因此产生 `datasources → qiming → fate` 的错误认知）。

## 反模式（门禁拦截对象）

1. datasources 产出 `character.sqlite3` 并宣称"供 fate 装载" —— 删除（fate 用 embed + dbinit，不读它）。
2. fate 仓内出现数据采集/清洗脚本 —— 门禁拦截。
3. qiming 部署声明 PG 但代码仍 `ent.Open("sqlite3", ...)` —— 不接受"声明与实现脱节"。
4. 运行时 DB 二进制入库 —— 不入库，走 build 生成或 Release 分发。
5. 同一字库被多处各自生成且无 sha256 契约校验 —— 以 character.json 为准。

## 部署形态与运行时方言

- fate：本地 sqlite（`fate` 文件，build 生成），无容器化要求。
- qiming：目标方言为 PostgreSQL 16（容器化，`deploy/docker-compose.yml`）；
  本地开发允许 sqlite 作为 fallback，但**代码必须同时实现 PG 路径**，不得只写 env 声明。
  付费表（users/orders/memberships/...）由 qiming 自管，与字库表同库不同表组。
