from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from trainops_observability.logging import configure_logging

from trainops_api.routes import router


def create_app() -> FastAPI:
    configure_logging("trainops-api")
    app = FastAPI(title="TrainOps TUI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()


def run() -> None:
    uvicorn.run("trainops_api.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    run()

