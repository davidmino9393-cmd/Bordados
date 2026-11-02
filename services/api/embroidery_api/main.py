"""Uvicorn entry point; configuration is private and read from the environment."""
import uvicorn

from .app import create_app
from .config import ApiConfig


app = create_app(ApiConfig.from_env())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
