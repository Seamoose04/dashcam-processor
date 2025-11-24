# CentralTaskQueue — Design & Architecture

This document explains the internal structure, behavior, and guarantees provided by `CentralTaskQueue`. This is one of the most critical components of the pipeline because it connects **VideoReaders** → **GPU workers** → **CPU workers** in a multiprocess-safe way.

Use this document if you need to debug queue behavior, add new task categories, or optimize throughput.

---

# 1. Purpose

The `CentralTaskQueue` is the in-memory coordination layer that:

* Stores tasks created by VideoReaders and Dispatcher
* Allows workers to pop tasks grouped by category
* Tracks backlog (per-category and global)
* Ensures multiprocess-safe operations

It does **not**:

* Persist data (that’s SQLite’s job)
* Perform scheduling (handled by workers choosing busiest categories)
* Track dependencies
* Store frames

---

# 2. Queue Structure

Internally, the queue maintains **one FIFO bucket per TaskCategory**.

A simplified conceptual structure:

```
queue = {
    "vehicle_yolo": deque([(task_id, task), ...]),
    "plate_yolo":   deque([...]),
    "ocr":          deque([...]),
    "plate_smooth": deque([...]),
    "summary":      deque([...]),
    ...
}
```

Each bucket is fully independent.
Workers only consume from their allowed buckets.

---

# 3. Operations

## 3.1 push(task_id, task)

Adds a task to the end of the category bucket.

### Guarantees:

* FIFO ordering within category
* Safe from multiple producers (VideoReaders + Dispatcher)
* O(1) amortized

---

## 3.2 pop(category)

Removes the next task for the given category.

### Returns:

```python
task, task_id
```

If the bucket is empty, returns `(None, None)`.

### Guarantees:

* Only workers who are allowed to process the category call pop
* Workers must check for `None` and retry
* Pops are atomic

---

## 3.3 backlog(category)

Returns the number of queued tasks for that category.

Used by:

* Worker selection (`choose busiest category`)
* VideoReader backpressure logic

---

## 3.4 total_backlog()

Returns the sum of all category backlogs.

Used by main thread to decide:

* When the pipeline is empty
* When workers can be terminated

---

# 4. Multiprocess Safety

The queue is built using:

* A Manager-backed dictionary for buckets
* Each bucket as a Manager-backed list or deque structure
* Locks around push/pop operations

This ensures that:

* Multiple readers and dispatchers can safely push tasks
* Multiple workers across many processes can safely pop tasks

SQLite operations happen **outside** of queue locks to avoid blocking.

---

# 5. Worker Interaction

## GPU Workers

* Poll all GPU categories
* Choose category with largest backlog
* Pop from that category

## CPU Workers

* Same logic but limited to CPU categories

Workers call:

```
cat = choose_busiest()
task, task_id = pop(cat)
```

This design:

* Avoids a central scheduler
* Keeps workers dynamic and load-balanced

---

# 6. Backpressure

VideoReaders pause when:

```
sum(queue.backlog(cat) for cat in gpu_categories) > MAX_GPU_BACKLOG
```

and similar logic for CPU categories.

This prevents:

* RAM blowup
* Queue saturation
* Overproduction when GPU is slower than input

Backpressure is **essential** to prevent frame ingestion from outrunning processing capacity.

---

# 7. Why Not a Single Global Queue?

A single queue would cause:

* Head-of-line blocking
* CPU tasks starving GPU tasks (or vice versa)
* No category-based load balancing
* Heavy contention

By having **N independent queues**, workers self-balance.

---

# 8. Future Extensions

You may want to add:

## Priority Levels

Each category bucket could become:

```
{ "high": deque(), "normal": deque(), ... }
```

## Batch Pops

GPU workers could pop batches of tasks for faster model inference.

## Remote Queue

If the system extends to multiple machines, replace Manager queues with:

* Redis
* ZeroMQ
* RabbitMQ
* Custom gRPC-based dispatcher

---

# 9. Summary

The CentralTaskQueue is:

* Multiprocess-safe
* Category-organized
* FIFO within each category
* The central backbone linking producers and workers

It supports the pipeline’s dynamic, scalable, and parallel processing architecture and ensures smooth flow from ingestion to GPU/CPU processing.

---