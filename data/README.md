# Data Production Pipeline

> 本仓（datasources）是字库数据的**生产方**。fate（CE）/ qiming（EE）是消费方，
> 通过数据产物消费，不通过代码 import。

## 目录结构

```
datasources/
├── data/
│   ├── README.md              # 本文件：数据生产流水线
│   ├── DATA_SOURCES.md         # 来源归属、许可、版本
│   └── download/               # 下载脚本（幂等）
│       ├── chinese_poetry.py   # clone/pull chinese-poetry
│       ├── unihan.py           # 下载 Unicode Unihan
│       └── xinhua.py           # 下载新华字典 word.json
├── entity/ent/schema/
│   └── character.go            # 20 字段消费契约（唯一真相源的 schema 表达）
├── scripts/
│   ├── verify_dataset.py       # 契约校验器（与 fate 同一份判定标准）
│   └── build_artifacts.py      # 契约 + PG 灌库脚本生成器
└── dist/                       # 派生产物（gitignore，走 Release 分发）
    ├── character.json          # 20 字段中性契约（唯一真相源）
    ├── character.pg.sql        # qiming PG 运行时灌库脚本（派生，非契约）
    └── MANIFEST.json           # sha256 + 行数
```

## 生产链路

```
外部源                        下载脚本                        加工/派生                     消费方
────────────────────────────────────────────────────────────────────────────────────────────────
chinese-poetry (354MB) ─→ data/download/chinese_poetry.py ─┐
Unihan         (49MB)  ─→ data/download/unihan.py         ─┼→ character.json (契约，20 字段)
xinhua         (26MB)  ─→ data/download/xinhua.py         ─┘        │
                                                                    ├─→ build_artifacts.py
                                                                    │      └─→ character.pg.sql → qiming (EE) PG 灌库
                                                                    └─→ verify_dataset.py (契约门禁)
```

**关键点**：上位规则见 `docs/ARCH_CONTRACT.md`。`character.json` 是唯一数据契约，
pg.sql 是确定性派生的 qiming PG 灌库脚本（幂等），不是数据库产物、不是第二契约。
fate 不消费 pg.sql——它 embed `character.json` 后用 `cmd/dbinit` 自行生成运行时 sqlite。
数据库文件（sqlite / pg dump）是消费方的运行时产物，本仓不生产、不分发。
EE 富化字段（`common_level` / `gender_hint` / `has_poetry` / `is_ancient`）不进本仓。

## 幂等下载

```bash
python3 data/download/chinese_poetry.py   # 已存在则 git pull，否则 clone
python3 data/download/unihan.py           # 下载 Unihan.zip 并解压到 data/raw/unihan/
python3 data/download/xinhua.py           # 下载 word.json 到 data/xinhua/
```

所有脚本接受 `--target` 覆盖目标目录，重复执行不产生副作用。

## 来源归属

见 `DATA_SOURCES.md`：每个源的仓库、许可、版本、使用字段与下游用途均已登记。
