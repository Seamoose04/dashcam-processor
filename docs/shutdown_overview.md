# Dashcam Processing Pipeline — Shutdown Design

This document explains the shutdown architecture of the pipeline, why the two-event system exists, and how each component responds during shutdown. It also covers potential pitfalls and how the final design prevents dangling workers or deadlocks.

---

# 1. Goals of Shutdown

A correct shutdown sequence must:

1. **Stop producing new tasks** (video readers must stop reading frames)
2. **Allow in-flight tasks to finish**
3. **Drain the entire backlog** (all queues empty)
4. **Ensure all workers exit cleanly**
5. **Terminate dispatcher + scheduler safely**
6. **Avoid deadlocks** (especially with queues + SQLite)

To achieve this, the system uses a two-event shutdown model.

---

# 2. Two-Event Shutdown Model

The pipeline defines two global events:

---

## **1. `stop` — Stop producing new tasks**

Triggered by: **Ctrl+C**, SIGINT, SIGTERM.

Effects:

* VideoReader threads stop reading frames
* No new tasks are inserted into SQLite
* No new entries are pushed into CentralTaskQueue

Readers exit their loops immediately when:

```python
while not stop.is_set():
```

This guarantees the pipeline is no longer growing.

---

## **2. `terminate` — Force workers to exit**

Triggered by:

* Once the backlog reaches zero AND all workers are idle
* Or during cleanup after stop

Effects:

* All GPU workers exit their loops
* All CPU workers exit their loops
* Dispatcher exits
* Scheduler exits

Workers check:

```python
while not terminate.is_set():
```

Once set, all workers break out of their loops and end.

---

# 3. Why One Event Is Not Enough

If shutdown used only a single flag:

### Case A — Only `stop`

Workers would:

* Stop processing immediately
* Leaving queued tasks unprocessed
* Main thread would wait forever for backlog to drain

### Case B — Only `terminate`

Workers would:

* Exit immediately, even while tasks remain
* Backlog would never drain
* Tasks would be lost, leading to undefined state

### Case C — Only "no more backlog" condition

VideoReaders would continue producing tasks indefinitely.

**Therefore the two-event system is required.**

---

# 4. Main Thread Shutdown Sequence

The main thread coordinates the entire shutdown process.

### Step 1 — Receive Ctrl+C

```python
stop.set()
```

Readers stop feeding new frames.

### Step 2 — Wait for backlog to drain

```python
while queue.total_backlog() > 0:
    sleep(0.1)
```

This ensures every queued task has been processed and written to SQLite.

### Step 3 — Signal termination

```python
terminate.set()
```

Workers, dispatcher, and scheduler begin graceful exit.

### Step 4 — Join workers

```python
worker.join(timeout=2)
```

Ensures nothing is left hanging.

---

# 5. Component Shutdown Behavior

## 5.1 VideoReaders

Exit when `stop.is_set()`.

```
while not stop.is_set():
    read frame → enqueue
```

They do *not* wait for backlog; they simply finish immediately.

## 5.2 GPU and CPU Workers

Exit when `terminate.is_set()`.

```
while not terminate.is_set():
    pop task → run model → write result
```

Workers finish any current task but won’t take new ones.

## 5.3 Dispatcher

Checks `terminate` periodically.
Exits its main loop on termination.

## 5.4 Scheduler

Same as dispatcher.

---

# 6. Avoiding Deadlocks

A few dangerous states are handled by this design.

## Danger: Worker stops before backlog drains

**Prevented by:** workers run until `terminate`, not `stop`.

## Danger: Main thread waiting forever

Main thread only waits until `total_backlog == 0`.
Then it sets terminate.

## Danger: SQLite connections left open

Each worker owns its own SQLiteStorage instance and closes by process exit.

## Danger: FrameStore never cleaned

Dispatcher handles dependency cleanup until the last moment.

---

# 7. Full Shutdown Timeline

```
User presses Ctrl+C
↓
[MAIN] sets stop
↓
VideoReaders exit reading loops
↓
Workers finish in-flight tasks
↓
Backlog drains to zero
↓
[MAIN] sets terminate
↓
Workers exit their main loops
↓
Dispatcher stops
↓
Scheduler stops
↓
Main joins workers
↓
Program ends cleanly
```

---

# 8. Testing Clean Shutdown

To test gracefully:

1. Run pipeline normally
2. Wait until workers are busy
3. Press Ctrl+C
4. Confirm:

   * VideoReader logs show exiting
   * Workers keep processing until queues drain
   * No deadlocks
   * Final log says "Shutdown complete"

---

# 9. Summary

The shutdown system is built around the idea that:

* Readers must stop immediately (stop event)
* Workers must continue until all work is finished (terminate event)
* Main thread orchestrates the sequence

This design ensures safety, correctness, and zero data loss.

---
