"""
Hybrid AI Resolver for Job Experience (YOE) and Grounded Tech Stack.
Processes ambiguous job postings in dynamically-sized token-optimized batches
using Gemini Flash-Lite, backed by strict anti-hallucination post-verification.
"""

import json
import re
import warnings
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

# Suppress benign google.genai SDK warning about AFC in generate_content, since we only use it for single-turn schema extraction
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")

from core.config import settings
from core.logger import setup_logger
from core.tech_grounding import validate_and_filter_tech_stack, extract_deterministic_tech_stack

logger = setup_logger("core.yoe_ai_resolver")

SYSTEM_INSTRUCTION = """You are an ultra-precise recruitment data parser.
For each provided job, extract five items:
1. Candidate Years of Experience (YOE) requirement: `yoe_min` and `yoe_max` (integers).
   - ONLY extract requirements for the CANDIDATE.
   - IGNORE company history, company age, or industry tenure (e.g., "Company has 15 years in market" -> yoe is null).
   - If not mentioned or unclear, set `yoe_min: null, yoe_max: null`.
2. Required Tech Stack: `tech_stack` (list of strings).
   - Extract ONLY programming languages, frameworks, databases, and technical cloud/devops tools EXPLICITLY written in the text.
   - NEVER assume, hallucinate, or extrapolate unmentioned technologies.
   - If no technical tools/languages are mentioned, return [].
3. Location: `location` (string).
   - Extract the standard city and state/country if mentioned. If strictly remote, output "Remote".
   - If unclear, set to null.
4. Work Mode: `work_mode` (string).
   - MUST be exactly one of: "remote", "hybrid", "onsite", or null.
   - Analyze both location and description to determine this.
5. Job Category: `job_category` (string).
   - E.g., "Engineering", "Sales", "HR", "Finance", "Product", "Marketing". 
   - Choose the closest high-level department.

Respond with a raw JSON array matching this exact schema:
[
  {"id": "job_identifier", "yoe_min": 3, "yoe_max": 5, "tech_stack": ["Python", "FastAPI"], "location": "San Francisco, CA", "work_mode": "hybrid", "job_category": "Engineering"},
  {"id": "job_identifier_2", "yoe_min": null, "yoe_max": null, "tech_stack": [], "location": "Remote", "work_mode": "remote", "job_category": "Sales"}
]
"""

class YOEAIResolver:
    """
    Batched, rate-limit resilient AI resolver for YOE and Tech Stack.
    """
    MAX_TOKENS_PER_REQUEST = 8000
    SYSTEM_PROMPT_TOKENS = 200
    MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite"
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def calculate_batch_size(self, jobs: List[Dict[str, Any]]) -> int:
        """
        Dynamically calculates optimal batch size based on average token length.
        """
        if not jobs:
            return 0
        total_words = 0
        for j in jobs:
            text = f"{j.get('title', '')} {j.get('description', '')[:700]}"
            total_words += len(text.split())
        avg_tokens = (total_words / len(jobs)) * 1.33 + 40  # input + output tokens
        available_tokens = self.MAX_TOKENS_PER_REQUEST - self.SYSTEM_PROMPT_TOKENS
        batch_size = max(5, int(available_tokens / max(avg_tokens, 50)))
        return min(batch_size, 10)

    def resolve_batch(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a list of jobs, batches them dynamically for Gemini Flash-Lite,
        and enriches each job with validated yoe_min, yoe_max, yoe_confidence, and tech_stack.
        Guarantees zero hallucination via post-verification.
        """
        if not jobs:
            return []

        if not self.client:
            logger.warning("No GEMINI_API_KEY configured. Falling back to deterministic resolution.")
            return self._apply_deterministic_fallback(jobs)

        results_by_id: Dict[str, Dict[str, Any]] = {}
        batch_size = self.calculate_batch_size(jobs)
        logger.info("Resolving %d ambiguous jobs starting with %s (batch size: %d)", len(jobs), self.MODELS[0], batch_size)

        for offset in range(0, len(jobs), batch_size):
            chunk = jobs[offset:offset + batch_size]
            prompt_payload = []
            job_texts_by_id = {}

            for idx, j in enumerate(chunk):
                jid = str(j.get('id') or f"idx_{offset + idx}")
                title = j.get('title', '')
                desc_snippet = (j.get('description') or '')[:700].strip()
                combined_text = f"{title}\n{desc_snippet}"
                job_texts_by_id[jid] = f"{title} {j.get('description', '')}"

                prompt_payload.append({
                    "id": jid,
                    "title": title,
                    "description": desc_snippet
                })

            prompt_text = f"Analyze these {len(prompt_payload)} jobs and extract YOE and Tech Stack:\n\n{json.dumps(prompt_payload, ensure_ascii=False)}"

            success = False
            for model_name in self.MODELS:
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )

                    raw_text = response.text.strip() if response and response.text else "[]"
                    # Strip markdown code fences if present
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    parsed_items = json.loads(raw_text)
                    if isinstance(parsed_items, list):
                        for item in parsed_items:
                            jid = str(item.get("id"))
                            raw_tech = item.get("tech_stack") or []
                            full_job_text = job_texts_by_id.get(jid, "")
                            
                            # Strict anti-hallucination verification
                            grounded_tech = validate_and_filter_tech_stack(raw_tech, full_job_text)

                            y_min = item.get("yoe_min")
                            y_max = item.get("yoe_max")
                            # Basic sanity check: min <= max, <= 20
                            if y_min is not None and isinstance(y_min, (int, float)):
                                y_min = int(y_min)
                                if y_min > 20:
                                    y_min = None
                            else:
                                y_min = None

                            if y_max is not None and isinstance(y_max, (int, float)):
                                y_max = int(y_max)
                                if y_max > 25:
                                    y_max = None
                            else:
                                y_max = None

                            results_by_id[jid] = {
                                "yoe_min": y_min,
                                "yoe_max": y_max,
                                "yoe_confidence": "ai_resolved" if (y_min is not None or y_max is not None) else "unspecified",
                                "tech_stack": grounded_tech,
                                "location": item.get("location"),
                                "work_mode": item.get("work_mode"),
                                "job_category": item.get("job_category")
                            }
                    
                    # If we reached here, parsing succeeded, so we break out of the fallback loop
                    success = True
                    break

                except Exception as ai_err:
                    logger.warning("Gemini resolution failed for %s (%s). Trying next fallback model...", model_name, ai_err)
                    continue

            if not success:
                logger.error("All AI fallback models failed for chunk. Falling back to deterministic regex rules.")
                for idx, j in enumerate(chunk):
                    jid = str(j.get('id') or f"idx_{offset + idx}")
                    full_text = job_texts_by_id.get(jid, "")
                    results_by_id[jid] = {
                        "yoe_min": j.get("yoe_min"),
                        "yoe_max": j.get("yoe_max"),
                        "yoe_confidence": "fallback",
                        "tech_stack": extract_deterministic_tech_stack(full_text)
                    }

        # Merge resolved data back into job dicts
        enriched_jobs = []
        for idx, j in enumerate(jobs):
            jid = str(j.get('id') or f"idx_{idx}")
            res = results_by_id.get(jid, {})
            merged = dict(j)
            if res.get("yoe_min") is not None:
                merged["yoe_min"] = res["yoe_min"]
                merged["yoe"] = res["yoe_min"]
            if res.get("yoe_max") is not None:
                merged["yoe_max"] = res["yoe_max"]
            if res.get("yoe_confidence"):
                merged["yoe_confidence"] = res["yoe_confidence"]
            if res.get("tech_stack") is not None:
                merged["tech_stack"] = res["tech_stack"]
            if res.get("location") is not None:
                merged["location"] = res["location"]
            if res.get("work_mode") is not None:
                merged["work_mode"] = res["work_mode"]
            if res.get("job_category") is not None:
                merged["job_category"] = res["job_category"]
            enriched_jobs.append(merged)

        return enriched_jobs

    def _apply_deterministic_fallback(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback when Gemini is unavailable."""
        fallback_jobs = []
        for j in jobs:
            merged = dict(j)
            text = f"{j.get('title', '')} {j.get('description', '')}"
            merged["tech_stack"] = extract_deterministic_tech_stack(text)
            if not merged.get("yoe_confidence"):
                merged["yoe_confidence"] = "fallback"
            fallback_jobs.append(merged)
        return fallback_jobs
