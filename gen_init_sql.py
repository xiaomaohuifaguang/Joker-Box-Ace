"""从模型生成远程库初始化 SQL（当前仅支持 MySQL）

用法：python gen_init_sql.py  →  产出 sql/mysql_init.sql

SQL 由 SQLAlchemy 的 MySQL 方言从模型直接编译，保证与代码永远一致——
新增/修改表模型后重跑本脚本即可，不要手改生成的 sql 文件。
"""
from pathlib import Path

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.core.db import Base

OUT = Path(__file__).parent / "sql" / "mysql_init.sql"


def main():
    OUT.parent.mkdir(exist_ok=True)
    dialect = mysql.dialect()
    stmts = []
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip()
        stmts.append(ddl + ";")
        # 索引（含 unique=True+index=True 生成的唯一索引）是独立语句，不能漏
        for idx in table.indexes:
            idx_ddl = str(CreateIndex(idx, if_not_exists=True).compile(dialect=dialect)).strip()
            stmts.append(idx_ddl + ";")

    OUT.write_text(
        "-- Joker Box Ace 远程库初始化 SQL（MySQL）\n"
        "-- 本文件由 gen_init_sql.py 从模型自动生成，请勿手改\n"
        "-- 建议库的字符集: utf8mb4 / utf8mb4_unicode_ci\n\n" + "\n\n".join(stmts) + "\n",
        encoding="utf-8",
    )
    print(f"✅ 生成 {OUT}（{len(stmts)} 张表）")


if __name__ == "__main__":
    main()
