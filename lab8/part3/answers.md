# Lab 8 Part 3 - Redpanda streaming consumer

## Setup
- docker-compose.yml starts Redpanda (1 broker) and Redpanda Console (http://localhost:8080).
- Topic payments, 3 partitions. producer.py replays the first 60 minutes of 2026-10-01 in receivedAt order and uses invoiceId as the message key, so all events of one payment go to the same partition. The hour holds 636 events: 208 / 204 / 224 in partitions 0 / 1 / 2 (Console, Partitions tab).
- consumer.py (confluent_kafka, consumer group, manual offset commit):
  - deduplication: key invoiceId + status + modifiedDate kept in a set; keys older than watermark minus 15 minutes are evicted;
  - event time = modifiedDate; tumbling 1-minute windows; only final events (success, failure) are counted; failure share per paymentMethod; alert when the share is above 10%;
  - watermark = (smallest of the per-partition maximum event times over all assigned partitions) minus allowed lateness (default 120 s); it never moves backwards; a window is closed when the watermark reaches its end; an event that belongs to a closed window is rejected as late;
  - every 500 events or 5 seconds the state (open windows, dedup set, watermark) is written to a checkpoint file and only then the offsets are committed (enable.auto.commit is off). After a restart the consumer continues from the last committed offset with the saved state, and events that are read again are removed by the dedup set.

## Correction of the first run
The first run rejected 404 of 636 events as late, although the dataset has only about 2% late events. Cause: one global watermark. Partition 0 was read first and moved the watermark to the end of the hour, so the events of partitions 1 and 2 (204 + 224 = 428) fell into already closed windows. The consumer now keeps the maximum event time per partition and uses the minimum over all assigned partitions. All numbers below are from the re-run with this fix.

## Results (636 events; allowed lateness 120 s unless stated)

| Run | consumed | duplicates dropped | late rejected | windows closed | alerts |
|---|---|---|---|---|---|
| Exp 1 baseline | 636 | 7 | 3 | 59 | 14 |
| Exp 1 crash + restart | 636 | 7 | 3 | 59 | 14 |
| Exp 2 worker-1 (partitions 0, 1) | 412 | 5 | 7 | 52 | 9 |
| Exp 2 worker-2 (partition 2) | 224 | 2 | 3 | 43 | 5 |
| Exp 3 fail-rate 0.3 | 636 | 7 | 7 | 59 | 59 |
| Exp 4 lateness 120 s | 636 | 7 | 3 | 59 | 14 |
| Exp 4 lateness 0 s | 636 | 7 | 4 | 59 | 14 |

### Experiment 1 - stop and restart
The consumer was started with --crash-at 300: it stops after 300 events without closing its open windows, and is then started again with the same checkpoint file. (The state is saved at that moment, so this tests restart from saved state and committed offsets, not a hard kill.) After the restart the totals equal the baseline: 636 consumed, 7 duplicates, 3 late, 59 windows, 14 alerts, 117 window records. The committed offsets are the same in both runs (208 / 204 / 224, lag 0; files exp1_offsets_baseline.txt and exp1_offsets_final.txt), so no event was lost and none was counted twice. One window record differs: the baseline has one apple_pay final event in the window starting 00:45, the restart run has one in the window starting 00:15 instead. Both runs reject 3 events as late. My hypothesis (not verified) is that which events are rejected as late depends on the order in which the partitions are polled, and this order is not identical after a restart.

### Experiment 2 - two consumers in one group
Two consumers in group payments-cg-two split the partitions: worker-1 got partitions 0 and 1, worker-2 got partition 2 (Console screenshot, Consumer Groups page; worker-2 was still reading, group offset 88 of 224). In the experiment run worker-1 consumed 412 events (208 + 204) and worker-2 224. Total 636, duplicates 7 (5 + 2), alerts 14 (9 + 5): the same as with one consumer, because the same invoiceId always goes to the same partition and therefore to the same consumer, so deduplication still works. Late events are 10 (7 + 3) against 3 with one consumer, because every consumer has its own watermark; I did not investigate this further. With 3 partitions at most 3 consumers of one group can work in parallel.

### Experiment 3 - producer with --fail-rate 0.3
The producer was run with --fail-rate 0.3 (the 30% failure injection required by the lab). Alerts rose from 14 to 59 and late events from 3 to 7; consumed (636) and duplicates (7) did not change.

### Experiment 4 - allowed lateness 0 s against 120 s
With lateness 0 the consumer rejected 4 events as late, with 120 s it rejected 3: one more event. Windows (59) and alerts (14) are the same. With lateness 0 a window is closed the moment the watermark reaches its end, so every later event for that window is dropped; with 120 s the window stays open 2 minutes longer. The difference is small here because the sample is only 636 events and the watermark is the minimum over three partitions, which already closes windows late.

## Limits
Only the first hour of one day was replayed. A partition that has no data (or is idle) holds the watermark back, so its windows are closed only at the final flush.

## Console screenshots
part3_console_topic_messages.png, part3_console_topic_partitions.png (3 partitions: 208 / 204 / 224), part3_console_group_two_members.png (two members of the group).
