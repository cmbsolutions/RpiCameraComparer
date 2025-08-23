from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime, timezone
from time import perf_counter_ns
from threading import RLock
from typing import Optional, Dict, Any
from contextlib import contextmanager

def _now_iso() -> str:
    # Wall clock in ISO 8601 with UTC offset (local time)
    return datetime.now().astimezone().isoformat(timespec="milliseconds")

def _ns_to_s(ns: int) -> float:
    return ns / 1_000_000_000.0

class PerfLogger:
    """
    Central logging + performance measurement.
    Call PerfLogger.get() anywhere to use the shared instance.
    """

    _instance: Optional["PerfLogger"] = None
    _inst_lock = RLock()

    @classmethod
    def get(cls) -> "PerfLogger":
        with cls._inst_lock:
            if cls._instance is None:
                cls._instance = PerfLogger()
            return cls._instance

    def __init__(self,
                 log_dir: Path | str = "logs",
                 app_name: str = "app",
                 also_console: bool = False) -> None:
        self._lock = RLock()
        self._app_start_ns = perf_counter_ns()
        self._tag_starts_ns: Dict[str, int] = {}

        # Ensure log directory exists
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        # File name with date + time
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"{app_name}_{ts}.log"
        self.log_path = log_dir / fname

        # Configure a dedicated logger
        self._logger = logging.getLogger(f"PerfLogger::{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # avoid duplicate prints

        # File handler
        fh = logging.FileHandler(self.log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        # Simple line format; we build structured message ourselves
        fmt = logging.Formatter("%(message)s")
        fh.setFormatter(fmt)
        self._logger.addHandler(fh)

        if also_console:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(fmt)
            self._logger.addHandler(ch)

        # Initial line showing start time
        self.log("Logger initialized", tag=None)

    # ---------- Core helpers ----------

    def _global_elapsed_s(self) -> float:
        return _ns_to_s(perf_counter_ns() - self._app_start_ns)

    def _local_elapsed_s(self, tag: str) -> Optional[float]:
        start = self._tag_starts_ns.get(tag)
        if start is None:
            return None
        return _ns_to_s(perf_counter_ns() - start)

    def _emit(self, message: str, tag: Optional[str], extra_fields: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            line = {
                "time": _now_iso(),                           # wall-clock
                "global_elapsed_s": round(self._global_elapsed_s(), 6),
                "tag": tag,
                "message": message
            }
            if tag is not None:
                le = self._local_elapsed_s(tag)
                if le is not None:
                    line["local_elapsed_s"] = round(le, 6)
            if extra_fields:
                line.update(extra_fields)

            # Write as a compact TSV (easy to parse) and human-friendly text.
            # You can switch to JSON if you prefer�just dump(line).
            fields = [
                f"time={line['time']}",
                f"global_elapsed_s={line['global_elapsed_s']}",
                f"tag={line['tag']}",
                f"message={line['message']}",
            ]
            if "local_elapsed_s" in line:
                fields.insert(2, f"local_elapsed_s={line['local_elapsed_s']}")
            

            # Include any extra fields deterministically
            for k in sorted(extra_fields.keys()) if extra_fields else []:
                if k not in {"time", "global_elapsed_s", "tag", "message", "local_elapsed_s"}:
                    fields.append(f"{k}={line[k]}")

            self._logger.info(" | ".join(fields))

    # ---------- Public API ----------

    def log(self, message: str, *, tag: Optional[str] = None, **extra: Any) -> None:
        """
        Write a log line with current wall time, global elapsed,
        and (if tag active) local elapsed.
        Extra keyword args get appended as key=value fields.
        """
        self._emit(message, tag, extra_fields=extra or None)

    def start_timer(self, tag: str, *, message: str = "timer started", **extra: Any) -> None:
        """
        Start (or restart) a local timer under `tag`.
        """
        with self._lock:
            self._tag_starts_ns[tag] = perf_counter_ns()
        self._emit(message, tag, extra_fields=extra or None)

    def tick(self, tag: str, message: str, **extra: Any) -> None:
        """
        Log a progress line for an active tag (does not stop it).
        """
        if tag not in self._tag_starts_ns:
            # Still log, but call out that the tag hasn't started yet
            self._emit(f"[WARN no active timer] {message}", tag, extra_fields=extra or None)
        else:
            self._emit(message, tag, extra_fields=extra or None)

    def stop_timer(self, tag: str, *, message: str = "timer stopped", **extra: Any) -> None:
        """
        Stop a local timer for `tag` and log a final line that includes the final local elapsed.
        """
        if tag not in self._tag_starts_ns:
            # Log anyway, so it's visible
            self._emit(f"[WARN no active timer] {message}", tag, extra_fields=extra or None)
            return
        # Capture elapsed before removing
        local_elapsed = self._local_elapsed_s(tag)
        with self._lock:
            self._tag_starts_ns.pop(tag, None)
        self._emit(message, tag, extra_fields={"final_local_elapsed_s": round(local_elapsed or 0.0, 6), **extra})

    # ---------- Sugar: decorator / context manager ----------

    @contextmanager
    def measure(self, tag: str, *, start_message: str = "timer started", stop_message: str = "timer stopped", **start_extra: Any):
        """
        Context manager for one-off measurements:

            with logger.measure("load_models"):
                load_all_models()

        Also usable as: for manual start/stop use start_timer/stop_timer.
        """
        self.start_timer(tag, message=start_message, **start_extra)
        try:
            yield
        except Exception as e:
            # Log failure with local elapsed included
            self._emit(f"exception: {type(e).__name__}: {e}", tag, extra_fields={"error": True})
            raise
        finally:
            self.stop_timer(tag, message=stop_message)