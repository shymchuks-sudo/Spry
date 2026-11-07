import argparse
import json
import os
import sys
import time
from pathlib import Path
import boto3

REGION = "us-east-1"
DATABASE = "lab8"
S3_OUTPUT = "s3://lab8-payments-594559484590/athena-results/"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
STATS_FILE = RESULTS_DIR / "query_stats.jsonl"

athena_client = boto3.client("athena", region_name=REGION)
s3_client = boto3.client("s3", region_name=REGION)


def parse_s3_uri(uri: str):
    uri_clean = uri[5:]
    bucket, key = uri_clean.split("/", 1)
    return bucket, key


def run_query(sql: str, database: str = DATABASE, query_name: str = "query") -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Starting Athena query '{query_name}'...")
    context = {"Database": database} if database else {}
    response = athena_client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext=context,
        ResultConfiguration={"OutputLocation": S3_OUTPUT},
    )
    query_id = response["QueryExecutionId"]
    print(f"Query ID: {query_id}")

    # Poll execution status
    while True:
        status_resp = athena_client.get_query_execution(QueryExecutionId=query_id)
        execution = status_resp["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)

    stats = execution.get("Statistics", {})
    data_scanned = stats.get("DataScannedInBytes", 0)
    engine_time_ms = stats.get("EngineExecutionTimeInMillis", 0)
    total_time_ms = stats.get("TotalExecutionTimeInMillis", 0)

    result_info = {
        "query_name": query_name,
        "query_id": query_id,
        "state": state,
        "data_scanned_bytes": data_scanned,
        "data_scanned_mb": round(data_scanned / (1024 * 1024), 4),
        "engine_time_ms": engine_time_ms,
        "total_time_ms": total_time_ms,
        "output_location": execution.get("ResultConfiguration", {}).get("OutputLocation", ""),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if state != "SUCCEEDED":
        reason = execution["Status"].get("StateChangeReason", "Unknown reason")
        result_info["error"] = reason
        print(f"Query {query_id} FAILED: {reason}")
        return result_info

    # Download output CSV if available
    s3_loc = result_info["output_location"]
    csv_dest = RESULTS_DIR / f"{query_name}.csv"
    if s3_loc and s3_loc.startswith("s3://"):
        bucket, key = parse_s3_uri(s3_loc)
        try:
            s3_client.download_file(bucket, key, str(csv_dest))
            result_info["csv_file"] = str(csv_dest.name)
            print(f"Result saved to {csv_dest}")
        except Exception as e:
            print(f"Warning: could not download CSV output: {e}")

    # Append to stats file
    with open(STATS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_info) + "\n")

    print(
        f"Query {query_name} SUCCEEDED | Scanned: {result_info['data_scanned_mb']} MB ({data_scanned} bytes) | "
        f"Run Time: {engine_time_ms} ms (Total: {total_time_ms} ms)"
    )
    return result_info


def main():
    parser = argparse.ArgumentParser(description="Run Athena SQL script and capture real metrics.")
    parser.add_argument("--sql-file", "-f", help="Path to SQL file")
    parser.add_argument("--sql", "-s", help="Inline SQL statement")
    parser.add_argument("--name", "-n", default=None, help="Descriptive name for the query")
    parser.add_argument("--database", "-d", default="default", help="Athena database")
    args = parser.parse_args()

    db = args.database if args.database else "default"

    if args.sql_file:
        sql_path = Path(args.sql_file)
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read().strip()
        name = args.name or sql_path.stem
    elif args.sql:
        sql_content = args.sql.strip()
        name = args.name or "inline_query"
    else:
        parser.error("Either --sql-file or --sql must be provided.")

    info = run_query(sql_content, database=db, query_name=name)
    if info["state"] != "SUCCEEDED":
        sys.exit(1)


if __name__ == "__main__":
    main()
