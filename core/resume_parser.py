import io
import os
import json
import re
from typing import Dict, Any, Optional
import PyPDF2
import docx
from google import genai
from google.genai import types

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Extracts plain text from PDF, DOCX, DOC, or TXT file bytes.
    """
    file_extension = os.path.splitext(filename)[1].lower()
    extracted_text = ""
    
    if file_extension == ".pdf":
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            extracted_text = "\n\n".join(pages_text)
        except Exception as read_error:
            raise ValueError(f"Failed to parse PDF document: {read_error}")
            
    elif file_extension in [".docx", ".doc"]:
        try:
            word_document = docx.Document(io.BytesIO(file_bytes))
            paragraph_lines = [p.text for p in word_document.paragraphs if p.text.strip()]
            for table in word_document.tables:
                for row in table.rows:
                    row_cells_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells_text:
                        paragraph_lines.append(" | ".join(row_cells_text))
            extracted_text = "\n".join(paragraph_lines)
        except Exception as read_error:
            raise ValueError(f"Failed to parse Word document: {read_error}")
            
    else:
        # Default plain text fallback
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="ignore")
            
    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        raise ValueError("The uploaded document contains no readable text or is image-based.")
        
    return cleaned_text

def extract_candidate_profile_heuristics(resume_text: str) -> Dict[str, Any]:
    """
    High-accuracy heuristic extractor that guarantees candidate metadata is
    never empty even if AI model experiences high-demand spikes (503) or latency.
    """
    resume_lines = [line.strip() for line in resume_text.split("\n") if line.strip()]
    
    # 1. Candidate Name: first non-header line that looks like a name
    candidate_name = "Candidate"
    for line in resume_lines[:5]:
        cleaned_line = re.sub(r"[^\w\s\.]", "", line).strip()
        words = cleaned_line.split()
        if 2 <= len(words) <= 4 and not re.search(r"resume|curriculum|vitae|email|phone|http|github|linkedin|page", cleaned_line, re.IGNORECASE):
            candidate_name = cleaned_line
            break
            
    # 2. Years of Experience
    years_of_experience = 2
    experience_regex_match = re.search(r"(\d+)\+?\s*(?:years|yrs)\s*(?:of\s*(?:professional\s*)?)?(?:experience|exp)", resume_text, re.IGNORECASE)
    if experience_regex_match:
        try:
            years_of_experience = int(experience_regex_match.group(1))
        except (ValueError, TypeError):
            pass
    else:
        # Detect year ranges like 2020 - Present
        year_ranges = re.findall(r"\b(201\d|202\d)\s*[-–—to]+\s*(Present|Current|202\d)\b", resume_text, re.IGNORECASE)
        if year_ranges:
            try:
                start_year = min(int(r[0]) for r in year_ranges)
                current_calendar_year = 2026
                calculated_years = current_calendar_year - start_year
                if 0 < calculated_years <= 30:
                    years_of_experience = calculated_years
            except Exception:
                pass

    # 3. Domain classification
    primary_domain = "Software Engineering"
    if re.search(r"full[\s-]stack", resume_text, re.IGNORECASE):
        primary_domain = "Full Stack"
    elif re.search(r"backend|distributed systems|microservices|golang|django|spring", resume_text, re.IGNORECASE):
        primary_domain = "Backend"
    elif re.search(r"frontend|ui\/ux|react|vue|angular|css", resume_text, re.IGNORECASE):
        primary_domain = "Frontend"
    elif re.search(r"devops|cloud|sre|infrastructure|kubernetes|terraform|aws", resume_text, re.IGNORECASE):
        primary_domain = "DevOps & Cloud"
    elif re.search(r"machine learning|data science|ai|deep learning|nlp|llm", resume_text, re.IGNORECASE):
        primary_domain = "AI / ML / Data"
    elif re.search(r"product manager|product management|scrum master", resume_text, re.IGNORECASE):
        primary_domain = "Product Management"

    # 4. Technical skills keyword matching
    standard_tech_keywords = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "Go", "Golang",
        "Java", "C++", "C#", "Rust", "AWS", "GCP", "Azure", "Docker", "Kubernetes",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Kafka", "GraphQL", "REST",
        "CI/CD", "Linux", "Terraform", "FastAPI", "Django", "Flask", "Next.js",
        "Vue", "Angular", "TailwindCSS", "SQL", "Git", "Microservices"
    ]
    matched_technical_skills = []
    for skill_keyword in standard_tech_keywords:
        boundary_pattern = r"\b" + re.escape(skill_keyword) + r"\b"
        if re.search(boundary_pattern, resume_text, re.IGNORECASE):
            matched_technical_skills.append(skill_keyword)

    # 5. Suggested Target Roles based on domain
    if primary_domain == "Full Stack":
        suggested_roles = ["Full Stack Engineer", "Senior Software Engineer", "Full Stack Developer"]
    elif primary_domain == "Backend":
        suggested_roles = ["Backend Engineer", "Senior Software Engineer", "Systems Engineer"]
    elif primary_domain == "Frontend":
        suggested_roles = ["Frontend Engineer", "UI Engineer", "Web Developer"]
    elif primary_domain == "AI / ML / Data":
        suggested_roles = ["Machine Learning Engineer", "AI Engineer", "Data Scientist"]
    elif primary_domain == "DevOps & Cloud":
        suggested_roles = ["DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer"]
    elif primary_domain == "Product Management":
        suggested_roles = ["Product Manager", "Technical Product Manager"]
    else:
        suggested_roles = ["Software Engineer", "Full Stack Engineer"]

    return {
        "candidate_name": candidate_name,
        "estimated_yoe": years_of_experience,
        "primary_domain": primary_domain,
        "top_skills": matched_technical_skills[:8] if matched_technical_skills else ["Python", "SQL", "Git"],
        "suggested_roles": suggested_roles
    }

def parse_candidate_resume_with_ai(resume_text: str, gemini_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Intelligently extracts candidate profile variables using Gemini AI with robust heuristic fallback.
    """
    heuristics = extract_candidate_profile_heuristics(resume_text)
    
    if not gemini_api_key or not resume_text:
        return heuristics
        
    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
    
    for model_name in candidate_models:
        try:
            client = genai.Client(api_key=gemini_api_key)
            truncated_text = resume_text[:5000]
            
            prompt = f"""
            Analyze the following resume and extract candidate profile attributes:
            
            --- RESUME TEXT ---
            {truncated_text}
            
            Extract strictly a JSON object with:
            - candidate_name (string: candidate full name)
            - estimated_yoe (integer: total years of experience, e.g. 1, 2, 3, 4...)
            - primary_domain (string: one of ["Software Engineering", "Full Stack", "Frontend", "Backend", "AI / ML / Data", "DevOps & Cloud", "Product Management"])
            - top_skills (array of strings: 5 to 8 most prominent technical skills, e.g. ["React", "Python", "AWS"])
            - suggested_roles (array of strings: 2 to 3 target job titles)
            
            Return ONLY valid JSON matching this schema.
            """
            
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            if response and response.text:
                data = json.loads(response.text)
                return {
                    "candidate_name": data.get("candidate_name") or heuristics["candidate_name"],
                    "estimated_yoe": int(data.get("estimated_yoe") or heuristics["estimated_yoe"]),
                    "primary_domain": data.get("primary_domain") or heuristics["primary_domain"],
                    "top_skills": data.get("top_skills") if data.get("top_skills") else heuristics["top_skills"],
                    "suggested_roles": data.get("suggested_roles") if data.get("suggested_roles") else heuristics["suggested_roles"]
                }
        except Exception:
            # Fall through to next model or heuristics
            continue

    return heuristics

# Backward compatibility aliases
extract_heuristics = extract_candidate_profile_heuristics
parse_resume_with_ai = parse_candidate_resume_with_ai
