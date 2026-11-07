import argparse
import json
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition


def parse_iso_utc(date_str: str) -> int:
    """Parse ISO 8601 UTC string to unix timestamp in seconds."""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return int(dt.timestamp())


def format_timestamp(ts: int) -> str:
    """Format unix timestamp to ISO 8601 UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StreamingConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topic: str,
        lateness_sec: int = 120,
        checkpoint_file: str = "lab8/part3/consumer_checkpoint.json",
        summary_file: str = "lab8/part3/results/consumer_summary.json",
        max_messages: int = None,
        idle_timeout_sec: float = 10.0,
        client_id: str = "consumer-1",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topic = topic
        self.lateness_sec = lateness_sec
        self.checkpoint_path = Path(checkpoint_file)
        self.summary_path = Path(summary_file)
        self.max_messages = max_messages
        self.crash_at = None
        self.idle_timeout_sec = idle_timeout_sec
        self.client_id = client_id

        # Streaming state
        self.max_event_time = 0
        self.watermark = 0
        # open_windows: window_start_ts -> { paymentMethod -> {"total": int, "failures": int} }
        self.open_windows = defaultdict(lambda: defaultdict(lambda: {"total": 0, "failures": 0}))
        self.closed_window_starts = set()
        # seen_events: dedup_key -> event_time
        self.seen_events = {}

        # Metrics / Counters
        self.events_consumed = 0
        self.duplicates_dropped = 0
        self.late_rejected = 0
        self.windows_closed = 0
        self.alerts_fired = 0
        self.closed_window_records = []

        # Load existing checkpoint if present
        self.load_checkpoint()

        # Kafka Consumer configuration
        conf = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "client.id": f"{self.group_id}-{self.client_id}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # Manual commit ONLY after checkpoint persistence
        }
        self.consumer = Consumer(conf)
        self.consumer.subscribe([self.topic])
        self.running = True

    def load_checkpoint(self):
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.max_event_time = data.get("max_event_time", 0)
                self.watermark = data.get("watermark", 0)
                self.events_consumed = data.get("events_consumed", 0)
                self.duplicates_dropped = data.get("duplicates_dropped", 0)
                self.late_rejected = data.get("late_rejected", 0)
                self.windows_closed = data.get("windows_closed", 0)
                self.alerts_fired = data.get("alerts_fired", 0)
                self.closed_window_records = data.get("closed_window_records", [])
                self.closed_window_starts = set(data.get("closed_window_starts", []))
                self.seen_events = data.get("seen_events", {})

                # Restore open_windows
                raw_windows = data.get("open_windows", {})
                for win_str, methods in raw_windows.items():
                    win_start = int(win_str)
                    for method, stats in methods.items():
                        self.open_windows[win_start][method] = {
                            "total": stats["total"],
                            "failures": stats["failures"],
                        }
                print(
                    f"[{self.client_id}] Restored state from checkpoint: "
                    f"consumed={self.events_consumed}, dedup_set_size={len(self.seen_events)}, "
                    f"watermark={format_timestamp(self.watermark) if self.watermark else 'N/A'}"
                )
            except Exception as e:
                print(f"Warning: Failed to load checkpoint: {e}", file=sys.stderr)

    def save_checkpoint(self):
        """Save consumer state atomically to disk, then commit offsets to Kafka."""
        state = {
            "max_event_time": self.max_event_time,
            "watermark": self.watermark,
            "events_consumed": self.events_consumed,
            "duplicates_dropped": self.duplicates_dropped,
            "late_rejected": self.late_rejected,
            "windows_closed": self.windows_closed,
            "alerts_fired": self.alerts_fired,
            "closed_window_starts": list(self.closed_window_starts),
            "closed_window_records": self.closed_window_records,
            "seen_events": self.seen_events,
            "open_windows": {
                str(win_start): dict(methods)
                for win_start, methods in self.open_windows.items()
            },
            "timestamp": time.time(),
        }

        # Write to temporary file first for atomic swap
        tmp_path = self.checkpoint_path.with_suffix(".tmp")
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        tmp_path.replace(self.checkpoint_path)

        # Commit Kafka offsets synchronously immediately after state is saved
        try:
            self.consumer.commit(asynchronous=False)
        except KafkaException as ke:
            # If no offset to commit yet, ignore
            pass

    def evict_old_seen_events(self):
        """Evict seen event keys older than watermark minus 15 minutes."""
        if not self.watermark:
            return
        cutoff = self.watermark - 15 * 60
        to_delete = [k for k, ts in self.seen_events.items() if ts < cutoff]
        for k in to_delete:
            del self.seen_events[k]

    def process_event(self, event: dict):
        self.events_consumed += 1

        inv_id = event["invoiceId"]
        status = event["status"]
        mod_date_str = event["modifiedDate"]
        event_time = parse_iso_utc(mod_date_str)
        method = event.get("paymentMethod", "unknown")

        # 1. Deduplication check (key: invoiceId + status + modifiedDate)
        dedup_key = f"{inv_id}:{status}:{mod_date_str}"
        if dedup_key in self.seen_events:
            self.duplicates_dropped += 1
            return
        self.seen_events[dedup_key] = event_time

        # 2. Advance event time & watermark
        if event_time > self.max_event_time:
            self.max_event_time = event_time
            self.watermark = self.max_event_time - self.lateness_sec

        # 3. Window routing (tumbling 1-minute window)
        win_start = (event_time // 60) * 60
        win_end = win_start + 60

        # If window is already closed (watermark passed window_end) or marked closed
        if win_start in self.closed_window_starts or (self.watermark > 0 and self.watermark >= win_end):
            self.late_rejected += 1
            return

        # 4. Aggregate terminal events
        if status in ("success", "failure"):
            self.open_windows[win_start][method]["total"] += 1
            if status == "failure":
                self.open_windows[win_start][method]["failures"] += 1

        # 5. Check if any open windows can now be closed
        self.check_and_close_windows()

        # 6. Evict old deduplication cache entries periodically
        if self.events_consumed % 1000 == 0:
            self.evict_old_seen_events()

    def check_and_close_windows(self):
        """Close windows where watermark >= window_end."""
        if self.watermark <= 0:
            return

        ready_starts = [
            ws for ws in sorted(self.open_windows.keys())
            if self.watermark >= (ws + 60)
        ]

        for ws in ready_starts:
            self.close_window(ws, label="WINDOW CLOSED")

    def close_window(self, win_start: int, label: str = "WINDOW CLOSED"):
        methods_data = self.open_windows.pop(win_start, {})
        self.closed_window_starts.add(win_start)
        self.windows_closed += 1

        win_str = format_timestamp(win_start)
        for method, stats in sorted(methods_data.items()):
            total = stats["total"]
            failures = stats["failures"]
            share_pct = (failures / total * 100.0) if total > 0 else 0.0
            rec = {
                "window_start": win_str,
                "label": label,
                "paymentMethod": method,
                "terminal_events": total,
                "failures": failures,
                "failure_share_pct": round(share_pct, 2),
                "alert": share_pct > 10.0,
            }
            self.closed_window_records.append(rec)

            alert_mark = " [ALERT > 10%]" if share_pct > 10.0 else ""
            print(
                f"[{label}] {win_str} | Method: {method:12} | "
                f"Terminal: {total:4} | Failures: {failures:3} | Share: {share_pct:5.2f}%{alert_mark}"
            )
            if share_pct > 10.0:
                self.alerts_fired += 1
                print(f"  *** ALERT: Failure share for {method} is {share_pct:.2f}% (exceeds 10.0% threshold) ***")

    def flush_open_windows(self):
        """Flush all remaining open windows at the end of execution."""
        remaining_starts = sorted(self.open_windows.keys())
        if remaining_starts:
            print("-" * 60)
            print(f"Flushing {len(remaining_starts)} remaining open windows at end of run...")
            for ws in remaining_starts:
                self.close_window(ws, label="WINDOW FLUSHED (END OF RUN)")
            print("-" * 60)

    def write_summary(self):
        """Write machine-readable summary JSON."""
        summary = {
            "client_id": self.client_id,
            "group_id": self.group_id,
            "topic": self.topic,
            "lateness_sec": self.lateness_sec,
            "events_consumed": self.events_consumed,
            "duplicates_dropped": self.duplicates_dropped,
            "late_rejected": self.late_rejected,
            "windows_closed": self.windows_closed,
            "alerts_fired": self.alerts_fired,
            "dedup_cache_size": len(self.seen_events),
            "max_event_time": format_timestamp(self.max_event_time) if self.max_event_time else None,
            "watermark": format_timestamp(self.watermark) if self.watermark else None,
            "window_records_count": len(self.closed_window_records),
            "window_records": self.closed_window_records,
        }
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary written to {self.summary_path}")

    def run(self):
        print(
            f"Starting StreamingConsumer [{self.client_id}] for topic '{self.topic}', group '{self.group_id}' "
            f"(allowed lateness={self.lateness_sec}s)..."
        )
        last_checkpoint_time = time.time()
        last_msg_time = time.time()
        start_time = time.time()
        startup_grace_period = 5.0

        try:
            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    now = time.time()
                    # Check idle timeout (allowing initial startup grace period)
                    if (now - start_time > startup_grace_period) and (now - last_msg_time > self.idle_timeout_sec):
                        print(f"[{self.client_id}] No messages received for {self.idle_timeout_sec}s. Exiting loop.")
                        break
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        print(f"Kafka error: {msg.error()}", file=sys.stderr)
                        break

                last_msg_time = time.time()
                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    self.process_event(payload)
                except Exception as ex:
                    print(f"Error parsing message: {ex}", file=sys.stderr)

                if self.crash_at and self.events_consumed >= self.crash_at:
                    self.save_checkpoint()
                    self.write_summary()
                    print(f"[{self.client_id}] *** CRASH TRIGGERED at {self.events_consumed} events! Stopping abruptly without flushing open windows ***")
                    self.consumer.close()
                    self.running = False
                    return

                # Periodic state checkpointing (every 5 seconds or every 500 events)
                now = time.time()
                if self.events_consumed % 500 == 0 or (now - last_checkpoint_time >= 5.0):
                    self.save_checkpoint()
                    last_checkpoint_time = now

                if self.max_messages and self.events_consumed >= self.max_messages:
                    print(f"[{self.client_id}] Reached max messages limit ({self.max_messages}). Stopping.")
                    break

        except KeyboardInterrupt:
            print(f"[{self.client_id}] Interrupted by user.")
        finally:
            if not (self.crash_at and self.events_consumed >= self.crash_at):
                self.flush_open_windows()
                self.evict_old_seen_events()
                self.save_checkpoint()
                self.write_summary()
            if self.consumer:
                try:
                    self.consumer.close()
                except Exception:
                    pass
                self.consumer = None

            print("=" * 60)
            print(f"Consumer [{self.client_id}] Final Execution Summary:")
            print(f"  Events Consumed:    {self.events_consumed}")
            print(f"  Duplicates Dropped: {self.duplicates_dropped}")
            print(f"  Late Rejected:      {self.late_rejected}")
            print(f"  Windows Closed:     {self.windows_closed}")
            print(f"  Alerts Fired:       {self.alerts_fired}")
            print(f"  Dedup Set Size:     {len(self.seen_events)}")
            print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Lab 8 Part 3: Streaming Event-Time Consumer")
    parser.add_argument("--bootstrap-servers", default="localhost:19092", help="Kafka broker address")
    parser.add_argument("--group-id", default="payments-cg", help="Consumer group ID")
    parser.add_argument("--topic", default="payments", help="Kafka topic")
    parser.add_argument("--lateness", type=int, default=120, help="Allowed lateness in seconds")
    parser.add_argument(
        "--checkpoint-file",
        default="lab8/part3/consumer_checkpoint.json",
        help="Path to state checkpoint file",
    )
    parser.add_argument(
        "--summary-file",
        default="lab8/part3/results/consumer_summary.json",
        help="Path to summary JSON output",
    )
    parser.add_argument("--max-messages", type=int, default=None, help="Stop after consuming N messages")
    parser.add_argument("--crash-at", type=int, default=None, help="Simulate sudden process crash at N events without flush")
    parser.add_argument("--idle-timeout", type=float, default=6.0, help="Idle seconds before shutdown")
    parser.add_argument("--client-id", default="c1", help="Consumer client identifier")
    args = parser.parse_args()

    consumer = StreamingConsumer(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topic=args.topic,
        lateness_sec=args.lateness,
        checkpoint_file=args.checkpoint_file,
        summary_file=args.summary_file,
        max_messages=args.max_messages,
        idle_timeout_sec=args.idle_timeout,
        client_id=args.client_id,
    )
    if args.crash_at:
        consumer.crash_at = args.crash_at
    consumer.run()


if __name__ == "__main__":
    main()
