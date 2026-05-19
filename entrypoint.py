import os
import resource
import signal
import sys

from aihub.config import get_settings
from aihub.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(
    debug=settings.server.debug,
    silence_probes=settings.server.silence_probes,
).bind(module=__name__)

from aihub.main import app  # noqa: E402, F401


def _log_worker_info():
    pid = os.getpid()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = usage.ru_maxrss / 1024 if sys.platform == "linux" else usage.ru_maxrss / (1024 * 1024)
    logger.info("worker_started", pid=pid, ppid=os.getppid(), rss_mb=round(rss_mb, 1))


def _on_signal(sig, frame):
    logger.warning("worker_signal_received", pid=os.getpid(), signal=signal.Signals(sig).name)
    sys.exit(128 + sig)


for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(_sig, _on_signal)

_log_worker_info()


if __name__ == "__main__":
    import uvicorn

    logger.info(
        "starting_server",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
    )
    uvicorn.run(
        "entrypoint:app",
        workers=settings.server.workers,
        host=settings.server.host,
        port=settings.server.port,
        timeout_keep_alive=settings.server.timeout_keep_alive,
        reload=settings.server.debug,
        log_level="debug" if settings.server.debug else "info",
    )
