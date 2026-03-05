import logging
import traceback

# ==================== Central Logger ====================
# لاگر مرکزی — همه فایل‌ها از این استفاده می‌کنن
# logging.basicConfig اینجا تنظیم نمیشه چون main.py مدیریتش می‌کنه

def get_logger(name: str) -> logging.Logger:
    """یه logger با نام مشخص برگردون"""
    return logging.getLogger(name)


# ==================== Log Helper Functions ====================

def log_info(logger: logging.Logger, loc: str, msg: str):
    logger.info(f"[{loc}] {msg}")

def log_error(logger: logging.Logger, loc: str, msg: str, exc: Exception = None):
    if exc:
        logger.error(
            f"[{loc}] ❌ {msg}\n"
            f"  {type(exc).__name__}: {exc}\n"
            f"{traceback.format_exc()}"
        )
    else:
        logger.error(f"[{loc}] ❌ {msg}")

def log_success(logger: logging.Logger, loc: str, msg: str):
    logger.info(f"[{loc}] ✅ {msg}")

def log_warn(logger: logging.Logger, loc: str, msg: str):
    logger.warning(f"[{loc}] ⚠️  {msg}")
