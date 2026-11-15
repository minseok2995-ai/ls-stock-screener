#!/usr/bin/env python3
"""scripts/migration_v24_watchlist_holdings.sql 내용을 common.js 의 MIGRATION_SQL 상수에 동기화합니다."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
sql = (ROOT / "scripts" / "migration_v24_watchlist_holdings.sql").read_text(encoding="utf-8")
p = ROOT / "common.js"
js = p.read_text(encoding="utf-8")
new, n = re.subn(r"const MIGRATION_SQL = [^\n]*;\n", lambda m: "const MIGRATION_SQL = " + json.dumps(sql, ensure_ascii=False) + ";\n", js, count=1)
assert n == 1, "MIGRATION_SQL 상수를 찾지 못했습니다."
p.write_text(new, encoding="utf-8")
print("synced", len(sql), "chars")
