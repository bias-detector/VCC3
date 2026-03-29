import atexit
import multiprocessing as mp
import os
import threading


def _burn_cpu(stop_event) -> None:
    value = 1
    while not stop_event.is_set():
        value = (value * 3 + 7) % 10000019


class CpuStressController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: list[mp.Process] = []
        self._events: list[mp.synchronize.Event] = []
        atexit.register(self.stop)

    def start(self, workers: int | None = None) -> dict:
        with self._lock:
            if self.is_active():
                return {
                    "started": False,
                    "active": True,
                    "workers": len(self._processes),
                    "message": "CPU stress is already running",
                }

            if workers is None:
                workers = os.cpu_count() or 1
            workers = max(1, int(workers))

            self._events = [mp.Event() for _ in range(workers)]
            self._processes = []

            for event in self._events:
                proc = mp.Process(target=_burn_cpu, args=(event,), daemon=True)
                proc.start()
                self._processes.append(proc)

            return {
                "started": True,
                "active": True,
                "workers": len(self._processes),
                "message": f"Started CPU stress with {len(self._processes)} workers",
            }

    def stop(self) -> dict:
        with self._lock:
            if not self.is_active():
                self._clear_state()
                return {
                    "stopped": False,
                    "active": False,
                    "workers": 0,
                    "message": "CPU stress is not running",
                }

            for event in self._events:
                event.set()

            for proc in self._processes:
                proc.join(timeout=2)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=1)

            workers = len(self._processes)
            self._clear_state()
            return {
                "stopped": True,
                "active": False,
                "workers": 0,
                "message": f"Stopped CPU stress ({workers} workers)",
            }

    def status(self) -> dict:
        with self._lock:
            active = self.is_active()
            return {
                "active": active,
                "workers": len(self._processes) if active else 0,
            }

    def is_active(self) -> bool:
        return any(proc.is_alive() for proc in self._processes)

    def _clear_state(self) -> None:
        self._processes = []
        self._events = []


stress_controller = CpuStressController()
