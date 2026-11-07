import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

import boto3


def fail_hash(invoice_id):
    # the same invoice always gets the same number, so all its events stay consistent
    return int(hashlib.md5(invoice_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--stream", default="lab8-payments-stream")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--fail-rate", type=float, default=0.0)
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    events = []
    with open(args.file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    events.sort(key=lambda e: e["receivedAt"])        # replay in processing-time order
    events = events[args.offset: args.offset + args.limit]
    print(f"replaying {len(events)} events, fail-rate {args.fail_rate}")

    kinesis = boto3.client("kinesis", region_name=args.region)
    sent = 0
    started = time.time()
    for i in range(0, len(events), 500):               # put_records takes at most 500 records
        records = []
        for e in events[i:i + 500]:
            if args.fail_rate > 0 and e["status"] in ("success", "failure") and fail_hash(e["invoiceId"]) < args.fail_rate:
                e = dict(e, status="failure", finalAmount=0, failureReason="Simulated failure")
            # the newline matters: without it Firehose glues the JSON objects together
            data = (json.dumps(e, ensure_ascii=False) + "\n").encode("utf-8")
            records.append({"Data": data, "PartitionKey": e["invoiceId"]})
        attempt = 0
        while records:
            resp = kinesis.put_records(StreamName=args.stream, Records=records)
            failed = resp["FailedRecordCount"]
            sent += len(records) - failed
            if failed == 0:
                break
            records = [r for r, res in zip(records, resp["Records"]) if "ErrorCode" in res]  # retry only the failed ones
            attempt += 1
            time.sleep(min(0.2 * 2 ** attempt, 5))
        time.sleep(0.6)                                # one shard accepts about 1000 records per second
    seconds = time.time() - started
    run = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "offset": args.offset, "limit": args.limit, "fail_rate": args.fail_rate,
        "sent": sent, "seconds": round(seconds, 1), "records_per_second": round(sent / seconds, 1),
    }
    print(run)
    with open("results/producer_runs.jsonl", "a", encoding="utf-8") as out:
        out.write(json.dumps(run) + "\n")


main()
