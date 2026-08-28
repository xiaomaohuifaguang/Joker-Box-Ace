"""数据库切换验证脚本：对当前配置的库跑全链路自检

用法：python db_check.py

- 今天对着 SQLite 跑通
- 未来切远程库那天：改 .env 指向远程库，跑同一个脚本，绿了才上线

覆盖：连接 → 建表 → 增 → 查 → 改 → 删 → 事务回滚 → 外键行为
"""
import asyncio
import sys

from sqlalchemy import Integer, MetaData, String, Table, Column, delete, insert, select, text, update

from app.core.db import DB_URL, engine

# 自检专用临时表（只用通用类型——这本身就是可移植性约束的演示）
_meta = MetaData()
check_table = Table(
    "_db_check", _meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(64), nullable=False),
)


async def main() -> int:
    print(f"目标库: {DB_URL.split('@')[-1]}")
    async with engine.begin() as conn:
        await conn.run_sync(_meta.drop_all)      # 幂等：先清掉上次残留
        await conn.run_sync(_meta.create_all)
        print("✅ 连接 + 建表")

        r = await conn.execute(insert(check_table).values(name="alice"))
        row_id = r.inserted_primary_key[0]
        print(f"✅ 插入 (id={row_id})")

        row = (await conn.execute(select(check_table).where(check_table.c.id == row_id))).first()
        assert row and row.name == "alice", "查询结果不符"
        print("✅ 查询")

        await conn.execute(update(check_table).where(check_table.c.id == row_id).values(name="bob"))
        row = (await conn.execute(select(check_table).where(check_table.c.id == row_id))).first()
        assert row.name == "bob", "更新结果不符"
        print("✅ 更新")

        await conn.execute(delete(check_table).where(check_table.c.id == row_id))
        assert (await conn.execute(select(check_table))).first() is None
        print("✅ 删除")

    # 事务回滚：独立事务里插入后主动回滚，数据不应存在
    async with engine.connect() as conn:
        trans = await conn.begin()
        await conn.execute(insert(check_table).values(name="ghost"))
        await trans.rollback()
        assert (await conn.execute(select(check_table))).first() is None, "回滚失败"
        print("✅ 事务回滚")

        fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar() if DB_URL.startswith("sqlite") else None
        if fk is not None:
            assert fk == 1, "SQLite 外键 PRAGMA 未开启"
            print("✅ SQLite 外键已开启（与远程库行为对齐）")

    async with engine.begin() as conn:
        await conn.run_sync(_meta.drop_all)      # 收尾清理
    await engine.dispose()
    print("\n🎉 全部通过，当前数据库配置可用")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
