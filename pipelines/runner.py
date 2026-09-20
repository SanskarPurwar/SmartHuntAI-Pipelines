import argparse
import concurrent.futures
import warnings
from typing import Dict, List, Type, Optional

# Suppress benign google.genai SDK warning about AFC in generate_content, since we only use it for single-turn schema extraction
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")

from core.logger import setup_logger
from pipelines.base_pipeline import BaseJobPipeline, PipelineRunResult
from pipelines.greenhouse import GreenhousePipeline
from pipelines.lever import LeverPipeline
from pipelines.ashby import AshbyPipeline
from pipelines.remotive import RemotivePipeline
from pipelines.linkedin import LinkedInPipeline
from pipelines.indeed import IndeedPipeline
from pipelines.yc import YCPipeline
from pipelines.smartrecruiters import SmartRecruitersPipeline

logger = setup_logger("pipelines.runner")

PIPELINE_REGISTRY: Dict[str, Type[BaseJobPipeline]] = {
    "greenhouse": GreenhousePipeline,
    "lever": LeverPipeline,
    "ashby": AshbyPipeline,
    "smartrecruiters": SmartRecruitersPipeline,
    "linkedin": LinkedInPipeline,
    "indeed": IndeedPipeline,
    "yc": YCPipeline,
    "remotive": RemotivePipeline,
}

def get_available_pipelines() -> List[Dict[str, str]]:
    """
    Returns metadata list of all decoupled pipelines registered in the engine.
    """
    results = []
    for code, cls in PIPELINE_REGISTRY.items():
        # Instantiate lightweight metadata instance
        instance = cls()
        results.append({
            "code": code,
            "name": instance.pipeline_name,
            "platform_code": instance.platform_code
        })
    return results

def run_pipeline(name: str, **kwargs) -> PipelineRunResult:
    """
    Executes a single pipeline by code name in strict isolation.
    """
    pipeline_key = name.strip().lower()
    pipeline_class = PIPELINE_REGISTRY.get(pipeline_key)

    if not pipeline_class:
        err_msg = f"Unknown pipeline '{name}'. Available: {list(PIPELINE_REGISTRY.keys())}"
        logger.error(err_msg)
        return PipelineRunResult(
            pipeline_name=name,
            platform_code=name,
            status="failed",
            jobs_fetched=0,
            new_jobs_added=0,
            duration_seconds=0.0,
            error_message=err_msg
        )

    logger.info("Initializing runner execution for pipeline '%s'...", pipeline_key)
    pipeline_instance = pipeline_class(**kwargs)
    return pipeline_instance.run()

def run_all_pipelines(parallel: bool = True, max_workers: int = 4) -> List[PipelineRunResult]:
    """
    Executes all registered pipelines either concurrently using a thread pool
    or sequentially. Even if one pipeline fails, others continue unaffected.
    """
    logger.info("Executing all %d pipelines (parallel=%s)...", len(PIPELINE_REGISTRY), parallel)
    results: List[PipelineRunResult] = []

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(run_pipeline, code): code
                for code in PIPELINE_REGISTRY.keys()
            }
            for future in concurrent.futures.as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    logger.error("Fatal runner uncaught error executing '%s': %s", code, exc)
                    results.append(PipelineRunResult(
                        pipeline_name=code,
                        platform_code=code,
                        status="failed",
                        jobs_fetched=0,
                        new_jobs_added=0,
                        duration_seconds=0.0,
                        error_message=str(exc)
                    ))
    else:
        for code in PIPELINE_REGISTRY.keys():
            results.append(run_pipeline(code))

    logger.info("All pipeline executions complete. Evaluated %d pipelines.", len(results))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Job Pipelines Unified Orchestrator")
    parser.add_argument("--pipeline", type=str, help="Specific pipeline code to run (e.g. greenhouse, lever, ashby, remotive)")
    parser.add_argument("--all", action="store_true", help="Run all registered pipelines")
    parser.add_argument("--list", action="store_true", help="List all available pipelines")

    args = parser.parse_args()

    if args.list:
        print("\nRegistered Pipelines:")
        for p in get_available_pipelines():
            print(f"  - [{p['code']}] {p['name']}")
    elif args.pipeline:
        print(f"\nExecuting single pipeline: {args.pipeline}")
        res = run_pipeline(args.pipeline)
        print(f"Result: {res.status} | Fetched: {res.jobs_fetched} | Added: {res.new_jobs_added} | {res.duration_seconds}s")
    elif args.all:
        print("\nExecuting all pipelines concurrently...")
        all_res = run_all_pipelines(parallel=True)
        for r in all_res:
            print(f"  - [{r.platform_code}] Status: {r.status} | Fetched: {r.jobs_fetched} | Added: {r.new_jobs_added} | {r.duration_seconds}s")
    else:
        parser.print_help()
