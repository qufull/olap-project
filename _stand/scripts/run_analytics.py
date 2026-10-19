from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "olap.duckdb"
CANONICAL_SQL = BASE_DIR / "sql" / "canonical_metric.sql"
ANALYTICS_SQL = BASE_DIR / "sql" / "analytics.sql"


def main():
  con = duckdb.connect(str(DB_PATH), read_only=True)

  print("=== ЭТАЛОН ГЛАВНОЙ МЕТРИКИ (sql/canonical_metric.sql) ===")
  con.sql(CANONICAL_SQL.read_text(encoding="utf-8")).show()

  # Разбиваем analytics.sql по запросам (разделитель ';')
  queries = [
      q.strip()
      for q in ANALYTICS_SQL.read_text(encoding="utf-8").split(";")
      if q.strip()
  ]

  for idx, q in enumerate(queries, 1):
    print(f"\n=== АНАЛИТИЧЕСКИЙ ЗАПРОС {idx} (Вопрос {idx}) ===")
    con.sql(q).show(max_rows=30)

  con.close()


if __name__ == "__main__":
  main()