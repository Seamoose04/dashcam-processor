# test_pipeline.py (excerpt)

from multiprocessing import Manager

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.tasks.fake_task import heavy_cpu_operation
from pipeline.workers.cpu_worker_mp import CPUWorkerProcess
from pipeline.scheduler import SchedulerProcess
from pipeline.dispatcher import DispatcherProcess
from pipeline.dispatch_handlers import handle_fake_cpu_result


def main():
    queue = CentralTaskQueue()
    db_path = "pipeline.db"
    db = SQLiteStorage(db_path)

    manager = Manager()
    worker_status = manager.dict()

    # CPU categories for this test
    cpu_categories = [TaskCategory.FAKE_CPU_TEST]

    resource_loaders = {
        TaskCategory.FAKE_CPU_TEST: lambda: None,
    }

    def fake_cpu_processor(task: Task, resource):
        n = task.payload.get("n", 1_000_000)
        return heavy_cpu_operation(n=n)

    processors = {
        TaskCategory.FAKE_CPU_TEST: fake_cpu_processor,
    }

    # enqueue some tasks
    for i in range(100):
        t = Task(
            category=TaskCategory.FAKE_CPU_TEST,
            payload={"n": 500_000 + i * 100_000},
            priority=0,
        )
        task_id = db.save_task(t)
        queue.push(task_id, t)

    # spawn CPU workers
    workers = []
    for wid in range(24):
        w = CPUWorkerProcess(
            worker_id=wid,
            task_queue=queue,
            db_path=db_path,
            cpu_categories=cpu_categories,
            resource_loaders=resource_loaders,
            processors=processors,
            worker_status=worker_status,
        )
        w.start()
        workers.append(w)

    # scheduler HUD
    scheduler = SchedulerProcess(
        task_queue=queue,
        worker_status=worker_status,
        interval=1.0,
    )
    scheduler.start()

    # dispatcher
    handlers = {
        TaskCategory.FAKE_CPU_TEST: handle_fake_cpu_result,
        # later: TaskCategory.OCR: handle_ocr_result, etc.
    }
    dispatcher = DispatcherProcess(
        db_path=db_path,
        task_queue=queue,
        handlers=handlers,
        interval=0.5,
    )
    dispatcher.start()

    # wait for workers
    for w in workers:
        w.join()

    # in a real system you’d have a graceful stopping condition;
    # for now, kill scheduler + dispatcher once workers exit
    scheduler.terminate()
    scheduler.join()
    dispatcher.terminate()
    dispatcher.join()


if __name__ == "__main__":
    main()
