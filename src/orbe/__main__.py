"""Run the reading desk."""

import uvicorn

from orbe.config.settings import get_settings


def main() -> None:
    """Serve the API. Access logs stay off so questions are not written to disk."""

    settings = get_settings()
    uvicorn.run(
        "orbe.main:app",
        host=settings.app_host,
        port=settings.app_port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
