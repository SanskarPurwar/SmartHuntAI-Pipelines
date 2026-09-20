import os
import json
import time
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

from core.config import settings
from core.db import get_db_cursor
from core.model_router import ModelRouter

GEMINI_API_KEY = settings.GEMINI_API_KEY

class AIJobEvaluator:
    """
    Performs AI-driven compensation estimation, candidate fit scoring,
    and automated tailored resume generation using tiered Gemini models.
    """

    def __init__(self, *args, resumes_dir: Optional[str] = None, user_id: Optional[int] = None, **kwargs):
        # Backward compatibility for legacy positional signature: (db_path, resumes_dir, user_id)
        if len(args) >= 2:
            self.tailored_resumes_directory = args[1]
        elif resumes_dir:
            self.tailored_resumes_directory = resumes_dir
        else:
            self.tailored_resumes_directory = str(settings.TAILORED_RESUMES_DIR)

        self.user_id = user_id or kwargs.get('user_id')
        self.model_router = ModelRouter(user_id=self.user_id)
        
        if GEMINI_API_KEY:
            self.ai_client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            self.ai_client = None

        self.master_resume_text = ""
        self.user_configuration = {}
        
        # Load user configuration and master resume
        if self.user_id:
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT config, master_resume FROM users WHERE id = %s", (self.user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    self.user_configuration = user_row.get('config') or {}
                    self.master_resume_text = user_row.get('master_resume') or ""

    def batch_evaluate_compensation_and_fit(self, logger=None) -> None:
        """
        Evaluates batches of enriched job postings to estimate compensation bounds,
        currency, and candidate fit score against the user's master resume.
        """
        def log_message(msg):
            if logger:
                logger(msg)
            else:
                print(msg)
            
        if not self.ai_client:
            log_message("[WARN] [Valuation] No GEMINI_API_KEY provided. Skipping AI compensation valuation.")
            return

        if not self.user_id:
            log_message("[WARN] [Valuation] AIJobEvaluator requires a valid user_id.")
            return

        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    gj.id::text AS id, 
                    gj.title, 
                    COALESCE(c.name, '') AS company, 
                    gj.description AS full_description, 
                    gj.description 
                FROM candidate_job_states cjs
                JOIN global_jobs gj ON cjs.job_id = gj.id
                LEFT JOIN companies c ON gj.company_id = c.id
                WHERE cjs.status = 'enriched' AND cjs.user_id = %s
            """, (self.user_id,))
            enriched_jobs = cursor.fetchall()
        
        if not enriched_jobs:
            log_message("[INFO] [Valuation] No eligible enriched jobs found for compensation modeling.")
            return
            
        batch_size = 5
        total_batches = (len(enriched_jobs) + batch_size - 1) // batch_size
        log_message(f"[INFO] [Valuation] Commencing batch compensation modeling & fit analysis for {len(enriched_jobs)} roles in {total_batches} batches...")
        
        for batch_offset in range(0, len(enriched_jobs), batch_size):
            job_batch = enriched_jobs[batch_offset:batch_offset + batch_size]
            current_batch_index = (batch_offset // batch_size) + 1
            
            try:
                selected_model_name = self.model_router.get_bulk_model()
            except Exception as routing_error:
                log_message(f"[ERROR] [Valuation] Model routing error: {routing_error}")
                break
                
            jobs_context_lines = []
            for job in job_batch:
                job_id = job['id']
                job_title = job.get('title', '')
                job_company = job.get('company', '')
                job_description = job.get('full_description') or job.get('description') or job_title
                # Truncate description to save tokens while preserving core qualifications
                jobs_context_lines.append(f"JOB_ID: {job_id} | TITLE: {job_title} | COMPANY: {job_company} | DESC: {job_description[:1000]}...")
                
            max_years_of_experience = self.user_configuration.get("max_yoe", 2)
            preferred_skills_str = ", ".join(self.user_configuration.get("preferred_skills", []))
            
            prompt = f"""
            You are a market salary estimator and expert recruiter. Estimate the salary for the following {len(job_batch)} jobs.
            Use the local currency of the job (e.g. INR for India, USD for US).
            Also give a match_score (0-100) based on my resume and preferred skills.
            
            IMPORTANT: Validate Year of Experience (YOE). The candidate has {max_years_of_experience} max YOE. 
            If the Job Title (e.g. Senior, Principal, Lead) or description implies a strict requirement of >{max_years_of_experience} YOE, set `is_over_experienced` to true.
            
            Preferred Skills to boost match_score (Not mandatory): {preferred_skills_str}
            
            --- MY RESUME ---
            {self.master_resume_text}
            
            --- JOBS ---
            {chr(10).join(jobs_context_lines)}
            
            Return strictly a JSON array of objects with keys:
            - job_id (string, exact UUID matching JOB_ID above)
            - min_salary (integer, e.g. 100000)
            - max_salary (integer, e.g. 150000)
            - currency (string, e.g. "INR" or "USD")
            - match_score (integer)
            - is_over_experienced (boolean)
            """
            
            try:
                log_message(f"[INFO] [Valuation] Dispatching Batch {current_batch_index}/{total_batches} ({len(job_batch)} roles) to {selected_model_name}...")
                response = self.ai_client.models.generate_content(
                    model=selected_model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                self.model_router.record_usage('bulk', 1)
                
                evaluation_results = json.loads(response.text)
                with get_db_cursor(commit=True) as update_cursor:
                    for evaluation in evaluation_results:
                        is_over_experienced = evaluation.get("is_over_experienced", False)
                        job_status = 'discarded' if is_over_experienced else 'evaluated'
                        is_qualified = not is_over_experienced
                        disqualification_reason = 'Candidate profile exceeds senior/lead qualification threshold' if is_over_experienced else None
                        target_job_id = str(evaluation.get("job_id"))
                        min_sal = evaluation.get("min_salary", 0)
                        max_sal = evaluation.get("max_salary", 0)
                        curr = evaluation.get("currency", "")
                        match_sc = evaluation.get("match_score", 0)
                        
                        update_cursor.execute("""
                            UPDATE global_jobs 
                            SET min_salary = %s, max_salary = %s, currency = %s, updated_at = NOW()
                            WHERE id = %s;
                            
                            UPDATE candidate_job_states
                            SET match_score = %s, status = %s, is_qualified = %s,
                                discard_reason = COALESCE(%s, discard_reason), updated_at = NOW()
                            WHERE job_id = %s AND user_id = %s;
                        """, (
                            min_sal, max_sal, curr, target_job_id,
                            match_sc, job_status, is_qualified, disqualification_reason, target_job_id, self.user_id
                        ))
                log_message(f"[INFO] [Valuation] Batch {current_batch_index}/{total_batches} processed successfully ({len(evaluation_results)} evaluated).")
            except Exception as batch_error:
                log_message(f"[ERROR] [Valuation] Batch {current_batch_index}/{total_batches} failed: {batch_error}")
                
            time.sleep(4) # Pacing interval for rate limit protection

    def generate_tailored_resume_for_job(self, job_id: int) -> Dict[str, Any]:
        """
        Generates a custom ATS-optimized Markdown resume tailored for a specific job posting
        using a premium Gemini tier.
        """
        if not self.ai_client:
            return {"error": "No GEMINI_API_KEY provided in configuration"}
            
        try:
            premium_model_name = self.model_router.get_premium_model()
        except Exception as quota_error:
            return {"error": str(quota_error)}
            
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    gj.title, 
                    COALESCE(c.name, '') AS company, 
                    gj.description AS full_description, 
                    gj.description 
                FROM candidate_job_states cjs
                JOIN global_jobs gj ON cjs.job_id = gj.id
                LEFT JOIN companies c ON gj.company_id = c.id
                WHERE gj.id = %s AND cjs.user_id = %s
            """, (str(job_id), self.user_id))
            job = cursor.fetchone()
        
        if not job:
            return {"error": "Target job posting not found or access denied"}
            
        job_title = job.get('title', '')
        job_company = job.get('company', '')
        job_description = job.get('full_description') or job.get('description') or job_title
        
        prompt = f"""
        You are an expert ATS (Applicant Tracking System) optimizer and recruiter.
        I will provide you with a candidate's Master Resume and a Job Description.
        
        Job Title: {job_title}
        Company: {job_company}
        
        --- JOB DESCRIPTION ---
        {job_description}
        
        --- MASTER RESUME ---
        {self.master_resume_text}
        
        Task: Rewrite the Master Resume to be highly tailored for this specific job. 
        Ensure it is ATS friendly, highlights relevant skills, and uses markdown format.
        Return strictly a JSON object with one key:
        - tailored_resume (string, in markdown format)
        """
        
        try:
            response = self.ai_client.models.generate_content(
                model=premium_model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            self.model_router.record_usage('premium', 1)
            
            result_json = json.loads(response.text)
            tailored_resume_markdown = result_json.get("tailored_resume", "")
            
            sanitized_company_name = "".join(c if c.isalnum() else "_" for c in job_company)
            output_filename = f"{job_id}_{sanitized_company_name}_resume.md"
            output_filepath = os.path.join(self.tailored_resumes_directory, output_filename)
            
            with open(output_filepath, "w", encoding="utf-8") as file_handle:
                file_handle.write(tailored_resume_markdown)
                
            with get_db_cursor(commit=True) as update_cursor:
                update_cursor.execute("""
                    UPDATE candidate_job_states 
                    SET tailored_resume_link = %s, is_tailored_resume = TRUE, updated_at = NOW() 
                    WHERE job_id = %s AND user_id = %s
                """, (output_filepath, str(job_id), self.user_id))
            return {"success": True, "path": output_filepath}
            
        except Exception as generation_error:
            return {"error": str(generation_error)}

    # Backward compatibility aliases
    process_salaries_bulk = batch_evaluate_compensation_and_fit
    tailor_resume_premium = generate_tailored_resume_for_job
    client = property(lambda self: self.ai_client)
    router = property(lambda self: self.model_router)
    resumes_dir = property(lambda self: self.tailored_resumes_directory)
    master_resume = property(lambda self: self.master_resume_text)
    config = property(lambda self: self.user_configuration)

# Backward compatibility alias
AIMatcher = AIJobEvaluator
