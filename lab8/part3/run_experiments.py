import json
import os
import subprocess
import sys
import time
from pathlib import Path

VENV_PYTHON = str(Path("lab8/.venv/Scripts/python.exe").resolve())
RESULTS_DIR = Path("lab8/part3/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd_list, capture=True) -> str:
    print(f">> Running: {' '.join(cmd_list)}")
    res = subprocess.run(cmd_list, capture_output=capture, text=True, check=True)
    return res.stdout


def recreate_topic(topic: str = "payments", partitions: int = 3):
    try:
        subprocess.run(["docker", "exec", "redpanda-0", "rpk", "topic", "delete", topic], capture_output=True)
    except Exception:
        pass
    time.sleep(1)
    res = subprocess.run(
        ["docker", "exec", "redpanda-0", "rpk", "topic", "create", topic, "-p", str(partitions)],
        capture_output=True,
        text=True,
    )
    print(f"Recreated topic {topic}: {res.stdout.strip()}")


def get_group_describe(group: str = "payments-cg") -> str:
    res = subprocess.run(
        ["docker", "exec", "redpanda-0", "rpk", "group", "describe", group],
        capture_output=True,
        text=True,
    )
    return res.stdout


def run_experiment_1():
    print("\n" + "=" * 80)
    print("EXPERIMENT 1: Baseline vs Crash & Restart (Exactly-Once Semantics)")
    print("=" * 80)

    # 1A: Baseline run
    print("\n--- Sub-experiment 1A: Clean Baseline Run ---")
    recreate_topic("payments", 3)
    ckpt_1a = RESULTS_DIR / "exp1_baseline_ckpt.json"
    if ckpt_1a.exists():
        ckpt_1a.unlink()

    # Produce first 60 minutes with high speed
    run_cmd([VENV_PYTHON, "lab8/part3/producer.py", "--minutes", "60", "--rate", "0", "--speedup", "0"])

    # Run consumer to completion
    log_1a = RESULTS_DIR / "exp1_baseline.log"
    cmd_consumer_1a = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-cg",
        "--checkpoint-file",
        str(ckpt_1a),
        "--summary-file",
        str(RESULTS_DIR / "exp1_baseline.json"),
        "--idle-timeout",
        "4.0",
        "--client-id",
        "c1-baseline",
    ]
    out_1a = run_cmd(cmd_consumer_1a)
    with open(log_1a, "w", encoding="utf-8") as f:
        f.write(out_1a)

    offsets_1a = get_group_describe("payments-cg")
    with open(RESULTS_DIR / "exp1_offsets_baseline.txt", "w", encoding="utf-8") as f:
        f.write(offsets_1a)
    print("Baseline offsets:\n" + offsets_1a)

    # 1B: Crash & Restart run on identical data
    print("\n--- Sub-experiment 1B: Crash Mid-Stream & Restart ---")
    recreate_topic("payments", 3)
    ckpt_1b = RESULTS_DIR / "exp1_restart_ckpt.json"
    if ckpt_1b.exists():
        ckpt_1b.unlink()

    # Produce same data
    run_cmd([VENV_PYTHON, "lab8/part3/producer.py", "--minutes", "60", "--rate", "0", "--speedup", "0"])

    # Phase 1: consume half (e.g. 300 messages), then crash abruptly
    print("Starting consumer phase 1 (crashing at 300 events)...")
    cmd_consumer_phase1 = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-cg",
        "--checkpoint-file",
        str(ckpt_1b),
        "--summary-file",
        str(RESULTS_DIR / "exp1_phase1.json"),
        "--crash-at",
        "300",
        "--client-id",
        "c1-phase1",
    ]
    out_p1 = run_cmd(cmd_consumer_phase1)

    offsets_crash = get_group_describe("payments-cg")
    with open(RESULTS_DIR / "exp1_offsets_crash.txt", "w", encoding="utf-8") as f:
        f.write(offsets_crash)
    print("Offsets after mid-stream stop (crash):\n" + offsets_crash)

    # Phase 2: restart consumer using same checkpoint file
    print("Restarting consumer phase 2 to process remaining data...")
    cmd_consumer_phase2 = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-cg",
        "--checkpoint-file",
        str(ckpt_1b),
        "--summary-file",
        str(RESULTS_DIR / "exp1_restart.json"),
        "--idle-timeout",
        "4.0",
        "--client-id",
        "c1-phase2",
    ]
    out_p2 = run_cmd(cmd_consumer_phase2)

    with open(RESULTS_DIR / "exp1_restart.log", "w", encoding="utf-8") as f:
        f.write(out_p1 + "\n\n--- CONSUMER RESTARTED ---\n\n" + out_p2)

    offsets_restart = get_group_describe("payments-cg")
    with open(RESULTS_DIR / "exp1_offsets_final.txt", "w", encoding="utf-8") as f:
        f.write(offsets_restart)
    print("Offsets after full restart completion:\n" + offsets_restart)


def run_experiment_2():
    print("\n" + "=" * 80)
    print("EXPERIMENT 2: Multi-Consumer Scalability & Partition Rebalancing")
    print("=" * 80)
    recreate_topic("payments", 3)

    ckpt_c1 = RESULTS_DIR / "exp2_c1_ckpt.json"
    ckpt_c2 = RESULTS_DIR / "exp2_c2_ckpt.json"
    if ckpt_c1.exists():
        ckpt_c1.unlink()
    if ckpt_c2.exists():
        ckpt_c2.unlink()

    cmd_c1 = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-cg",
        "--checkpoint-file",
        str(ckpt_c1),
        "--summary-file",
        str(RESULTS_DIR / "exp2_c1.json"),
        "--idle-timeout",
        "5.0",
        "--client-id",
        "worker-1",
    ]
    cmd_c2 = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-cg",
        "--checkpoint-file",
        str(ckpt_c2),
        "--summary-file",
        str(RESULTS_DIR / "exp2_c2.json"),
        "--idle-timeout",
        "5.0",
        "--client-id",
        "worker-2",
    ]

    print("Launching both consumers in group 'payments-cg'...")
    p1 = subprocess.Popen(cmd_c1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(cmd_c2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    print("Waiting 3s for consumer group rebalance and partition assignment...")
    time.sleep(3)

    # Capture group description showing partition assignment
    group_desc = get_group_describe("payments-cg")
    with open(RESULTS_DIR / "exp2_group_describe.txt", "w", encoding="utf-8") as f:
        f.write(group_desc)
    print("Consumer Group Partition Split:\n" + group_desc)

    print("Replaying messages now that consumers are active...")
    run_cmd([VENV_PYTHON, "lab8/part3/producer.py", "--minutes", "60", "--rate", "0", "--speedup", "0"])

    print("Waiting for consumers to finish processing and reach idle timeout...")
    try:
        out1, err1 = p1.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        p1.kill()
        out1, err1 = p1.communicate()
    try:
        out2, err2 = p2.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        p2.kill()
        out2, err2 = p2.communicate()

    with open(RESULTS_DIR / "exp2_c1.log", "w", encoding="utf-8") as f:
        f.write(out1)
    with open(RESULTS_DIR / "exp2_c2.log", "w", encoding="utf-8") as f:
        f.write(out2)
    print("Both workers completed successfully.")


def run_experiment_3():
    print("\n" + "=" * 80)
    print("EXPERIMENT 3: Deterministic Failure Injection (--fail-rate 0.3)")
    print("=" * 80)
    recreate_topic("payments", 3)
    ckpt_3 = RESULTS_DIR / "exp3_failrate_ckpt.json"
    if ckpt_3.exists():
        ckpt_3.unlink()

    # Produce with --fail-rate 0.3
    run_cmd(
        [
            VENV_PYTHON,
            "lab8/part3/producer.py",
            "--minutes",
            "60",
            "--fail-rate",
            "0.3",
            "--rate",
            "0",
            "--speedup",
            "0",
        ]
    )

    # Consume
    cmd_consumer_3 = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-fail-cg",
        "--checkpoint-file",
        str(ckpt_3),
        "--summary-file",
        str(RESULTS_DIR / "exp3_failrate.json"),
        "--idle-timeout",
        "4.0",
        "--client-id",
        "c1-failrate",
    ]
    out_3 = run_cmd(cmd_consumer_3)
    with open(RESULTS_DIR / "exp3_failrate.log", "w", encoding="utf-8") as f:
        f.write(out_3)
    print("Experiment 3 completed.")


def run_experiment_4():
    print("\n" + "=" * 80)
    print("EXPERIMENT 4: Allowed Lateness (120s vs 0s)")
    print("=" * 80)

    # 4A: Lateness 120 (Standard)
    recreate_topic("payments", 3)
    ckpt_4a = RESULTS_DIR / "exp4_lateness120_ckpt.json"
    if ckpt_4a.exists():
        ckpt_4a.unlink()

    run_cmd([VENV_PYTHON, "lab8/part3/producer.py", "--minutes", "60", "--rate", "0", "--speedup", "0"])

    cmd_4a = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-late120-cg",
        "--lateness",
        "120",
        "--checkpoint-file",
        str(ckpt_4a),
        "--summary-file",
        str(RESULTS_DIR / "exp4_lateness120.json"),
        "--idle-timeout",
        "4.0",
        "--client-id",
        "c1-late120",
    ]
    out_4a = run_cmd(cmd_4a)
    with open(RESULTS_DIR / "exp4_lateness120.log", "w", encoding="utf-8") as f:
        f.write(out_4a)

    # 4B: Lateness 0 (Strict)
    recreate_topic("payments", 3)
    ckpt_4b = RESULTS_DIR / "exp4_lateness0_ckpt.json"
    if ckpt_4b.exists():
        ckpt_4b.unlink()

    run_cmd([VENV_PYTHON, "lab8/part3/producer.py", "--minutes", "60", "--rate", "0", "--speedup", "0"])

    cmd_4b = [
        VENV_PYTHON,
        "lab8/part3/consumer.py",
        "--group-id",
        "payments-late0-cg",
        "--lateness",
        "0",
        "--checkpoint-file",
        str(ckpt_4b),
        "--summary-file",
        str(RESULTS_DIR / "exp4_lateness0.json"),
        "--idle-timeout",
        "4.0",
        "--client-id",
        "c1-late0",
    ]
    out_4b = run_cmd(cmd_4b)
    with open(RESULTS_DIR / "exp4_lateness0.log", "w", encoding="utf-8") as f:
        f.write(out_4b)

    print("Experiment 4 completed.")


def main():
    print("Starting automated execution of all Part 3 experiments...")
    run_experiment_1()
    run_experiment_2()
    run_experiment_3()
    run_experiment_4()
    print("\nALL 4 EXPERIMENTS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
