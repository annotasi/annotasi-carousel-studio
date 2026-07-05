#!/usr/bin/env python3
"""Annotasi Carousel Studio service entrypoint."""

from __future__ import annotations

import logging
import os
import sys
from http.server import ThreadingHTTPServer

from .config import AI_API_KEY, AI_BASE_URL, AI_MODEL, HOST, PORT, STORAGE_DIR
from .http.handler import AnnotasiHandler


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> int:
    configure_logging()
    logger = logging.getLogger("annotasi_carousel_studio")
    logger.info("service_starting host=%s port=%s storage_dir=%s", HOST, PORT, STORAGE_DIR)
    logger.info("ai_config base_url=%s model=%s api_key_configured=%s", AI_BASE_URL, AI_MODEL, bool(AI_API_KEY))
    server = ThreadingHTTPServer((HOST, PORT), AnnotasiHandler)
    sys.stdout.write(f"Annotasi Carousel Studio running on http://{HOST}:{PORT}\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("service_stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
