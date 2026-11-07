import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from confluent_kafka import Producer


def delivery_report(err, msg, stats):
    """Callback triggered on record delivery or error."""
    if err is not None:
        stats["failed"] += 1
        print(f"Message delivery failed: {err}", file=sys.stderr)
    else:
        stats["delivered"] += 1
        p = msg.partition()
        stats["partition_counts"][p] = stats["partition_counts"].get(p, 0) + 1


def is_invoice_failed(invoice_id: str, fail_rate: float) -> bool:
    """Deterministically decide if an invoice should fail based on MD5 hash."""
    if fail_rate <= 0.0:
        return False
    digest = hashlib.md5(invoice_id.encode("utf-8")).hexdigest()
    # Normalize to [0.0, 1.0)
    score = (int(digest[:8], 16)) / 0xFFFFFFFF
    return score < fail_rate


def main():
    parser = argparse.ArgumentParser(description="Lab 8 Part 3: Kafka/Redpanda Event Replay Producer")
    parser.add_argument("--bootstrap-servers", default="localhost:19092", help="Kafka broker address")
    parser.add_argument("--topic", default="payments", help="Kafka destination topic")
    parser.add_argument(
        "--input-file",
        default="lab8/data/dt=2026-10-01/events.jsonl",
        help="Input JSON Lines file path",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of events to produce")
    parser.add_argument("--minutes", type=float, default=None, help="Limit to first M minutes of data")
    parser.add_argument("--speedup", type=float, default=1.0, help="Replay speedup factor (0 or inf for max speed)")
    parser.add_argument("--rate", type=float, default=60.0, help="Target events per second (0 for unlimited)")
    parser.add_argument(
        "--fail-rate",
        type=float,
        default=0.0,
        help="Deterministic failure injection share (0.0 to 1.0)",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: input file '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading events from {input_path}...")
    events = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    print(f"Loaded {len(events)} events. Sorting by receivedAt...")
    events.sort(key=lambda x: x["receivedAt"])

    # Filter by minutes if requested
    if args.minutes is not None and args.minutes > 0 and len(events) > 0:
        start_time_iso = events[0]["receivedAt"]
        start_dt = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        cutoff_sec = args.minutes * 60.0
        filtered = []
        for e in events:
            cur_dt = datetime.fromisoformat(e["receivedAt"].replace("Z", "+00:00"))
            if (cur_dt - start_dt).total_seconds() <= cutoff_sec:
                filtered.append(e)
            else:
                break
        events = filtered
        print(f"Filtered to first {args.minutes} minutes: {len(events)} events.")

    if args.limit is not None and args.limit > 0:
        events = events[: args.limit]
        print(f"Filtered to limit of {args.limit} events.")

    total_events = len(events)
    if total_events == 0:
        print("No events to send.")
        return

    # Setup Kafka Producer
    conf = {
        "bootstrap.servers": args.bootstrap_servers,
        "client.id": "lab8-payment-producer",
        "linger.ms": 5,
        "batch.size": 65536,
        "compression.type": "snappy",
    }
    producer = Producer(conf)

    stats = {
        "delivered": 0,
        "failed": 0,
        "partition_counts": {},
    }

    print(
        f"Starting replay of {total_events} events to topic '{args.topic}' at {args.bootstrap_servers} "
        f"(fail_rate={args.fail_rate}, rate={args.rate}/s, speedup={args.speedup})..."
    )
    start_real_time = time.time()
    last_print = start_real_time

    # Calculate sleep interval if rate is configured
    sleep_interval = 0.0
    if args.rate > 0 and args.speedup > 0:
        sleep_interval = 1.0 / (args.rate * args.speedup)

    for i, event in enumerate(events):
        inv_id = event["invoiceId"]

        # Apply deterministic failure rate injection
        if args.fail_rate > 0.0 and is_invoice_failed(inv_id, args.fail_rate):
            # If this is the terminal event of the payment, turn it into failure
            if event["status"] in ("success", "failure"):
                event["status"] = "failure"
                event["finalAmount"] = 0
                if "failureReason" not in event or not event["failureReason"]:
                    event["failureReason"] = "Injected failure for experiment"

        value_bytes = json.dumps(event, ensure_ascii=False).encode("utf-8")
        key_bytes = inv_id.encode("utf-8")

        # Partition key = invoiceId ensures all events for the same invoice go to the same partition
        producer.produce(
            topic=args.topic,
            key=key_bytes,
            value=value_bytes,
            on_delivery=lambda err, msg: delivery_report(err, msg, stats),
        )

        # Periodically poll to serve delivery callbacks
        if i % 500 == 0:
            producer.poll(0)
            now = time.time()
            if now - last_print >= 2.0:
                print(f"Produced {i}/{total_events} events ({(i/total_events)*100:.1f}%)...")
                last_print = now

        if sleep_interval > 0:
            time.sleep(sleep_interval)

    # Flush remaining messages
    print("Flushing outstanding messages...")
    producer.flush(30)

    elapsed = time.time() - start_real_time
    rate = stats["delivered"] / elapsed if elapsed > 0 else 0

    print("=" * 60)
    print(f"Production Complete in {elapsed:.2f}s ({rate:.1f} events/s)")
    print(f"Total Produced: {stats['delivered']} | Delivery Failures: {stats['failed']}")
    print("Messages sent per partition:")
    for partition, count in sorted(stats["partition_counts"].items()):
        print(f"  Partition {partition}: {count} messages ({(count/stats['delivered'])*100:.2f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
