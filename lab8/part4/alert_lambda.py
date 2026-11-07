import base64
import json
import os
import time

import boto3

sns = boto3.client("sns")
TOPIC_ARN = os.environ["TOPIC_ARN"]
MIN_EVENTS = int(os.environ.get("MIN_EVENTS", "30"))     # ignore tiny samples
THRESHOLD = float(os.environ.get("THRESHOLD", "0.10"))   # alert above 10 %
COOLDOWN = 60                                            # seconds between alerts for one method
MAX_ALERTS = 5                                           # hard cap per container (no mailbox flood)

last_alert = {}
alerts_sent = 0


def handler(event, context):
    global alerts_sent
    stats = {}
    for rec in event["Records"]:
        text = base64.b64decode(rec["kinesis"]["data"]).decode("utf-8").strip()
        if not text:
            continue
        e = json.loads(text)
        if e.get("status") not in ("success", "failure"):
            continue  # only final statuses count
        s = stats.setdefault(e["paymentMethod"], {"terminal": 0, "failed": 0})
        s["terminal"] += 1
        if e["status"] == "failure":
            s["failed"] += 1

    now = time.time()
    for method, s in stats.items():
        share = s["failed"] / s["terminal"]
        print(json.dumps({"method": method, "terminal": s["terminal"], "failed": s["failed"], "share": round(share, 3)}))
        if s["terminal"] < MIN_EVENTS or share <= THRESHOLD:
            continue
        if alerts_sent >= MAX_ALERTS or now - last_alert.get(method, 0) < COOLDOWN:
            continue
        message = f"ALERT: {method} failure share {share:.0%} ({s['failed']} of {s['terminal']} final events in one batch)"
        resp = sns.publish(TopicArn=TOPIC_ARN, Subject="lab8 payment failure alert", Message=message)
        last_alert[method] = now
        alerts_sent += 1
        print("SNS published", resp["MessageId"], message)
    return {"batches": len(event["Records"])}
