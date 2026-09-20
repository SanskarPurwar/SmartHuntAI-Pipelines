# Backward compatibility proxy module
from repositories.pipeline_run_repository import PipelineRunRepository, RunRepository
__all__ = ['PipelineRunRepository', 'RunRepository']
