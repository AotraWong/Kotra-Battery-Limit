"""Immediate, timestamped application event logging."""
import logging
import sys

logger = logging.getLogger('kotra-battery-limit')
logger.addHandler(logging.NullHandler())
logger.propagate = False


def configure_logging(path):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.INFO)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding='utf-8')
    except OSError as exc:
        print(f'Cannot open log file: {exc}\n无法打开日志文件：{exc}', file=sys.stderr)
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [PID %(process)d] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)


def log_exception(exc_type, value, traceback):
    logger.error('Unhandled exception / 未处理异常', exc_info=(exc_type, value, traceback))
    sys.__excepthook__(exc_type, value, traceback)
