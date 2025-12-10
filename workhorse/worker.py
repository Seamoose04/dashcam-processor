import argparse
import logging
import shutil
import time
from pathlib import Path

from .config import Config
from .heavy_processor import HeavyProcessor
from .task_client import HttpTaskClient, TaskClientError

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, config: Config):
        self.config = config
        self.client = HttpTaskClient(config.server_url, api_key=config.api_key)
        self.processor = HeavyProcessor(config)

    def run_once(self) -> bool:
        task = self.client.fetch_next_task(self.config.task_type)
        if not task:
            log.info("No %s tasks available", self.config.task_type)
            return False
        log.info("Pulled task %s for video %s", task.task_id, task.video_id)
        result = self.processor.process(task)
        payload = result.to_payload()
        self.client.complete_task(task.task_id, payload)
        log.info(
            "Completed task %s; wrote metadata to %s",
            task.task_id,
            result.metadata_path,
        )
        return True

    def run_forever(self) -> None:
        while True:
            try:
                worked = self.run_once()
            except TaskClientError as exc:
                log.error("Task client error: %s", exc)
                worked = False
            except Exception as exc:  # noqa: BLE001
                log.exception("Unexpected error while processing task: %s", exc)
                worked = False
            if not worked:
                time.sleep(self.config.poll_interval_seconds)


def clear_scratch(config: Config) -> None:
    path = config.scratch_root
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="4090 workstation worker")
    parser.add_argument("--once", action="store_true", help="Process at most one task then exit")
    parser.add_argument("--skip-scratch-clean", action="store_true", help="Do not wipe scratch on startup")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    config = Config.from_env()
    config.ensure_dirs()
    if not args.skip_scratch_clean:
        clear_scratch(config)

    worker = Worker(config)
    if args.once:
        worker.run_once()
    else:
        worker.run_forever()


if __name__ == "__main__":
    main()
