"""Compatibility entry point for the integrated AGroup application."""
import os
from backend.server import create_app as create_shared_app


def create_app(config=None):
    return create_shared_app(config=config)


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
