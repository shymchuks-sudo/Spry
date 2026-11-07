import csv
import json
import sys
import time
from pathlib import Path

import boto3

OUT = "s3://lab8-payments-594559484590/athena-results/"
athena = boto3.client("athena", region_name="us-east-1")

path = Path(sys.argv[1])
qid = athena.start_query_execution(
    QueryString=path.read_text(encoding="utf-8"),
    QueryExecutionContext={"Database": "lab8"},
    ResultConfiguration={"OutputLocation": OUT},
)["QueryExecutionId"]
while True:
    q = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
    state = q["Status"]["State"]
    if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
        break
    time.sleep(1)
if state != "SUCCEEDED":
    print(state, q["Status"].get("StateChangeReason"))
    sys.exit(1)

rows = []
try:
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            rows.append([c.get("VarCharValue", "") for c in r["Data"]])
except Exception:
    pass  # DDL statements return no rows
if rows:
    with open(Path("results") / (path.stem + ".csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    for r in rows[:30]:
        print(" | ".join(r))
stats = q["Statistics"]
line = {"query": path.name, "query_id": qid, "scanned_bytes": stats.get("DataScannedInBytes"), "engine_ms": stats.get("EngineExecutionTimeInMillis")}
print(line)
with open("results/athena_stats.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(line) + "\n")
