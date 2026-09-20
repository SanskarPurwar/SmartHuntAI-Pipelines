"""
Decoupled Modular Job Ingestion Pipeline Architecture.
Each platform pipeline is completely isolated with its own client, seed registry, and error boundaries.
"""

from .base_pipeline import BaseJobPipeline, NormalizedJobDto, PipelineRunResult
from .runner import run_pipeline, run_all_pipelines, get_available_pipelines, PIPELINE_REGISTRY

__all__ = [
    "BaseJobPipeline",
    "NormalizedJobDto",
    "PipelineRunResult",
    "run_pipeline",
    "run_all_pipelines",
    "get_available_pipelines",
    "PIPELINE_REGISTRY"
]
