from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from lmq.config import PipelineConfig
from lmq.pipeline.run import PipelineGateError, run_pipeline

app = typer.Typer(no_args_is_help=True, add_completion=False)
pipeline_app = typer.Typer(no_args_is_help=True, add_completion=False)
qa_app = typer.Typer(no_args_is_help=True, add_completion=False)
eval_app = typer.Typer(no_args_is_help=True, add_completion=False)
report_app = typer.Typer(no_args_is_help=True, add_completion=False)
release_app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(qa_app, name="qa")
app.add_typer(eval_app, name="eval")
app.add_typer(report_app, name="report")
app.add_typer(release_app, name="release")


def _default_config_path() -> Path:
    return Path("configs/pipeline.yaml")


def _load_config(config: Path | None) -> tuple[Path, PipelineConfig]:
    cfg_path = config or _default_config_path()
    if not cfg_path.is_file():
        typer.echo(f"Config not found: {cfg_path}", err=True)
        raise typer.Exit(code=1)
    return cfg_path, PipelineConfig.load(cfg_path)


# ── pipeline ────────────────────────────────────────────────────────


@pipeline_app.command("run")
def pipeline_run(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
    raw_dir: Annotated[
        Path | None,
        typer.Option(
            "--raw-dir",
            help="Override raw_dir from config (e.g. data/raw_fail for a failing run)",
        ),
    ] = None,
) -> None:
    """Run bronze -> silver -> gold with per-layer gates (fail-fast)."""
    cfg_path, cfg = _load_config(config)
    try:
        manifest_path = run_pipeline(cfg, cfg_path, raw_dir)
    except PipelineGateError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Success. Manifest: {manifest_path}")


# ── qa ──────────────────────────────────────────────────────────────


@qa_app.command("build-index")
def qa_build_index(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
) -> None:
    """Build a ChromaDB vector index from the gold Parquet layer."""
    _, cfg = _load_config(config)
    gold_parquet = cfg.lake_root / "gold" / "gold.parquet"
    if not gold_parquet.is_file():
        typer.echo(f"Gold parquet not found: {gold_parquet}", err=True)
        typer.echo("Run 'lmq pipeline run' first.", err=True)
        raise typer.Exit(code=1)

    from lmq.rag.chunking import load_gold_chunks
    from lmq.rag.index import build_index

    chunks = load_gold_chunks(gold_parquet)
    count = build_index(chunks, cfg.rag.index_dir)
    typer.echo(f"Index built: {count} chunks in {cfg.rag.index_dir}")


@qa_app.command("ask")
def qa_ask(
    question: Annotated[str, typer.Argument(help="The question to ask")],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
    top_k: Annotated[
        int | None,
        typer.Option("--top-k", "-k", help="Number of chunks to retrieve"),
    ] = None,
) -> None:
    """Ask a question against the indexed gold corpus."""
    _, cfg = _load_config(config)
    k = top_k or cfg.rag.top_k

    from lmq.agent.run import ask

    result = ask(question, index_dir=cfg.rag.index_dir, top_k=k)
    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"Question: {result.question}")
    typer.echo(f"Mode:     {result.mode}")
    typer.echo(f"{'=' * 60}\n")
    typer.echo(result.answer)
    typer.echo(f"\n{'-' * 60}")
    typer.echo("Sources:")
    for s in result.sources:
        typer.echo(f"  - {s.doc_id}  chunk={s.chunk_index}  dist={s.distance:.4f}")
    typer.echo()


# ── eval ─────────────────────────────────────────────────────────────

_DEFAULT_GOLDEN = Path("tests/golden/qa_pairs.jsonl")


@eval_app.command("regression")
def eval_regression(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
    golden: Annotated[
        Path | None,
        typer.Option("--golden", "-g", help="Path to golden qa_pairs.jsonl"),
    ] = None,
    top_k: Annotated[
        int | None,
        typer.Option("--top-k", "-k", help="Chunks to retrieve per question"),
    ] = None,
) -> None:
    """Run regression tests against the golden QA set."""
    _, cfg = _load_config(config)
    golden_path = golden or _DEFAULT_GOLDEN
    if not golden_path.is_file():
        typer.echo(f"Golden set not found: {golden_path}", err=True)
        raise typer.Exit(code=1)

    from lmq.eval.regression import run_regression, write_report

    k = top_k or cfg.rag.top_k
    report = run_regression(golden_path, index_dir=cfg.rag.index_dir, top_k=k)
    artifact = write_report(report, cfg.artifacts_dir)

    typer.echo(f"\nRegression run: {report.run_id}")
    typer.echo(f"Total: {report.total}  Passed: {report.passed}  Failed: {report.failed}")
    typer.echo(f"Pass rate: {report.pass_rate:.1%}")
    if report.failed:
        typer.echo("\nFailed cases:")
        for c in report.cases:
            if not c.passed:
                typer.echo(f"  FAIL: {c.question}")
                if c.missing_keywords:
                    typer.echo(f"        missing keywords: {c.missing_keywords}")
                if c.missing_substrings:
                    typer.echo(f"        missing substrings: {c.missing_substrings}")
    typer.echo(f"\nArtifact: {artifact}")
    if report.pass_rate < 1.0:
        raise typer.Exit(code=1)


# ── report ───────────────────────────────────────────────────────────


@report_app.command("evidently")
def report_evidently(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
    baseline: Annotated[
        Path | None,
        typer.Option("--baseline", "-b", help="Baseline gold Parquet"),
    ] = None,
    current: Annotated[
        Path | None,
        typer.Option("--current", help="Current gold Parquet"),
    ] = None,
) -> None:
    """Generate an Evidently data-drift and quality report."""
    _, cfg = _load_config(config)
    gold_parquet = cfg.lake_root / "gold" / "gold.parquet"

    cur = current or gold_parquet
    base = baseline or gold_parquet
    for label, p in [("Baseline", base), ("Current", cur)]:
        if not p.is_file():
            typer.echo(f"{label} parquet not found: {p}", err=True)
            raise typer.Exit(code=1)

    from lmq.monitoring.evidently_reports import generate_report

    out_dir = cfg.artifacts_dir / "evidently"
    paths = generate_report(base, cur, out_dir)
    typer.echo(f"HTML report: {paths.html}")
    typer.echo(f"JSON summary: {paths.json_summary}")


# ── release ──────────────────────────────────────────────────────────


@release_app.command("evaluate")
def release_evaluate(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
) -> None:
    """Evaluate promotion readiness: reject / canary / production."""
    _, cfg = _load_config(config)

    from lmq.promotion.engine import discover_inputs, evaluate, write_result

    inputs = discover_inputs(cfg.artifacts_dir)
    result = evaluate(inputs, cfg.promotion)
    artifact = write_result(result, cfg.artifacts_dir)

    typer.echo(f"\nDecision:  {result.decision.upper()}")
    typer.echo("Reasons:")
    for r in result.reasons:
        typer.echo(f"  - {r}")
    typer.echo(f"\nThresholds: {result.thresholds}")
    typer.echo(f"Inputs:     {inputs.model_dump()}")
    typer.echo(f"\nArtifact: {artifact}")

    if result.decision == "reject":
        raise typer.Exit(code=1)


# ── serve ────────────────────────────────────────────────────────────


@app.command("serve")
def serve(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to pipeline.yaml"),
    ] = None,
    host: Annotated[str, typer.Option(help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port number")] = 8000,
) -> None:
    """Start the FastAPI QA server."""
    import uvicorn

    from lmq.serving.api import create_app

    cfg_path = config or _default_config_path()
    if not cfg_path.is_file():
        typer.echo(f"Config not found: {cfg_path}", err=True)
        raise typer.Exit(code=1)

    application = create_app(cfg_path)
    uvicorn.run(application, host=host, port=port)


# ── misc ────────────────────────────────────────────────────────────


@app.command("version")
def version() -> None:
    """Print package version."""
    from lmq import __version__

    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
