from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from lmq import __version__
from lmq.agent.run import ask
from lmq.config import PipelineConfig
from lmq.serving.schemas import HealthResponse, QARequest, QAResponse, SourceChunk


def create_app(config_path: Path | None = None) -> FastAPI:
    cfg_path = config_path or Path("configs/pipeline.yaml")
    cfg = PipelineConfig.load(cfg_path)

    from lmq.cloud.secrets_manager import load_secrets

    load_secrets(
        secret_name=cfg.cloud.secret_name if cfg.cloud else None,
        region=cfg.cloud.aws_region if cfg.cloud else None,
    )

    application = FastAPI(title="lmq", version=__version__)

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @application.post("/v1/qa", response_model=QAResponse)
    def qa(body: QARequest) -> QAResponse:
        top_k = body.top_k or cfg.rag.top_k
        result = ask(body.question, index_dir=cfg.rag.index_dir, top_k=top_k)
        return QAResponse(
            question=result.question,
            answer=result.answer,
            mode=result.mode,
            top_k=top_k,
            sources=[
                SourceChunk(
                    chunk_id=s.chunk_id,
                    doc_id=s.doc_id,
                    source_path=s.source_path,
                    chunk_index=s.chunk_index,
                    text=s.text,
                    distance=s.distance,
                )
                for s in result.sources
            ],
        )

    return application


app = create_app()
