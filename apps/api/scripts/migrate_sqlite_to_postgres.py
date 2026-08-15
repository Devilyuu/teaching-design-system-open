"""把 SQLite 里的数据整体搬到 PostgreSQL。

24 张表，**没有一条外键约束**（关联全靠代码里的 `task_id` 这类字段），
所以逐表整表复制就够，不必排依赖顺序。

**这里最容易漏的是序列。** SQLModel 的整数主键在 PostgreSQL 上是 SERIAL，
显式插入 id **不会推动它**。不补这一步，迁完当场查什么都对、页面也正常，
直到下一次新建课程撞上主键冲突——那时人已经在用了，排查起来完全看不出
和切库有关。所以本脚本迁完必定 setval，并且会把结果打出来。

加密字段（模型配置里的 API key）原样搬：密文是用 `MODEL_CONFIG_ENCRYPTION_KEY`
加的，只要那把 key 不变，换库不影响解密。**切库时别顺手换 key。**

用法（在 `apps/api` 目录下，用生产 venv 跑）：

    SOURCE_URL="sqlite:////var/lib/teaching-design-system/teaching_design.db" \\
    TARGET_URL="postgresql+psycopg://teaching:***@127.0.0.1:15434/teaching_design" \\
    MODEL_CONFIG_ENCRYPTION_KEY=x \\
    python scripts/migrate_sqlite_to_postgres.py

`--dry-run` 只读源库、报每张表的行数，不碰目标库。
目标库非空时默认拒绝执行，`--allow-nonempty` 才继续。
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, func, select, text
from sqlmodel import SQLModel

# 导入才会把 24 张表注册进 metadata；模块本身不直接用到
import app.models  # noqa: F401
from app.db import engine_options


def _engine(url: str):
    return create_engine(url, **engine_options(url))


def _row_counts(conn) -> dict:
    counts = {}
    for table in SQLModel.metadata.sorted_tables:
        counts[table.name] = conn.execute(select(func.count()).select_from(table)).scalar_one()
    return counts


def _resync_sequence(conn, table) -> str:
    """让序列从现有最大 id 之后继续。

    `setval(seq, n, false)` 的意思是「下一个取 n」，所以传 MAX+1。
    空表传 1，也就是从头开始。
    """
    pk = list(table.primary_key.columns)
    if len(pk) != 1:
        return "跳过（不是单列主键）"
    column = pk[0]
    if not isinstance(column.type.python_type, type) or column.type.python_type is not int:
        return "跳过（主键不是整数）"

    sequence = conn.execute(
        text("SELECT pg_get_serial_sequence(:table, :column)"),
        {"table": table.name, "column": column.name},
    ).scalar()
    if sequence is None:
        return "跳过（这一列没有序列）"

    largest = conn.execute(select(func.max(column))).scalar()
    following = (largest or 0) + 1
    conn.execute(text("SELECT setval(:seq, :value, false)"), {"seq": sequence, "value": following})
    return f"下一个 id = {following}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只读源库并报行数，不写目标")
    parser.add_argument(
        "--allow-nonempty",
        action="store_true",
        help="目标库已有数据时仍然继续（默认拒绝，避免迁进一个用过的库）",
    )
    args = parser.parse_args()

    source_url = os.environ.get("SOURCE_URL", "").strip()
    target_url = os.environ.get("TARGET_URL", "").strip()
    if not source_url:
        print("缺少 SOURCE_URL", file=sys.stderr)
        return 2
    if not args.dry_run and not target_url:
        print("缺少 TARGET_URL（--dry-run 时可以不给）", file=sys.stderr)
        return 2

    source = _engine(source_url)
    with source.connect() as conn:
        before = _row_counts(conn)

    total = sum(before.values())
    print(f"源库 {len([t for t in before if before[t]])} 张非空表，共 {total} 行")
    for name, count in sorted(before.items(), key=lambda item: -item[1]):
        if count:
            print(f"  {name:<28} {count}")

    if args.dry_run:
        print("\n--dry-run：没有写入任何东西")
        return 0

    target = _engine(target_url)
    SQLModel.metadata.create_all(target)

    with target.connect() as conn:
        existing = _row_counts(conn)
    if sum(existing.values()) and not args.allow_nonempty:
        print(
            f"\n目标库已有 {sum(existing.values())} 行数据，拒绝执行。"
            "\n确认要迁进这个库就加 --allow-nonempty",
            file=sys.stderr,
        )
        return 1

    print("\n开始复制")
    with source.connect() as src, target.begin() as dst:
        for table in SQLModel.metadata.sorted_tables:
            rows = src.execute(select(table)).mappings().all()
            if rows:
                dst.execute(table.insert(), [dict(row) for row in rows])
            print(f"  {table.name:<28} {len(rows)}")

    # 序列必须在数据写完之后同步，而且必须真的做——见模块开头
    print("\n同步序列")
    with target.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            print(f"  {table.name:<28} {_resync_sequence(conn, table)}")

    with target.connect() as conn:
        after = _row_counts(conn)

    print("\n逐表核对")
    mismatched = [name for name in before if before[name] != after.get(name)]
    for name in sorted(before):
        if before[name] or after.get(name):
            flag = "✓" if before[name] == after.get(name) else "✗"
            print(f"  {flag} {name:<28} 源 {before[name]} → 目标 {after.get(name)}")

    if mismatched:
        print(f"\n有 {len(mismatched)} 张表行数对不上：{'、'.join(mismatched)}", file=sys.stderr)
        return 1

    print(f"\n完成：{total} 行全部迁移，行数逐表一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
