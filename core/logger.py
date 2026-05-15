import logging
from pathlib import Path


logger = logging.getLogger("AQRS")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    try:
        Path("logs").mkdir(exist_ok=True)
        handler = logging.FileHandler("logs/system.log", encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
