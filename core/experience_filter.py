import re

class YearsOfExperienceFilter:
    """
    Evaluates whether a candidate qualifies for a job posting based on the
    years of experience specified in the job description.
    """

    def __init__(self, max_years_of_experience: int):
        self.max_years_of_experience = max_years_of_experience

    def is_candidate_qualified(self, job_description: str) -> bool:
        """
        Returns True if the job is valid (requires <= max_years_of_experience).
        Returns False if the job exceeds candidate's maximum experience ceiling.
        """
        if not job_description:
            return True
            
        from core.job_enrichment import RE_YOE_NEGATIVE
        # Strip out company history/tenure references so company age is never parsed as YOE
        normalized_text = RE_YOE_NEGATIVE.sub(' ', job_description.lower())
        extracted_minimum_experience_requirements = []
        
        # 1. Matches experience ranges like "1-3 years", "2 to 4 yrs"
        range_experience_matches = re.finditer(r'(\d+)\s*(?:-|to|–)\s*(\d+)\s*(?:years?|yrs?)', normalized_text)
        for match in range_experience_matches:
            extracted_minimum_experience_requirements.append(int(match.group(1)))
                
        # 2. Matches open-ended experience requirements like "3+ years", "5+ yrs"
        plus_experience_matches = re.finditer(r'(\d+)\s*\+\s*(?:years?|yrs?)', normalized_text)
        for match in plus_experience_matches:
            extracted_minimum_experience_requirements.append(int(match.group(1)))
                
        # 3. Matches minimum phrases like "minimum 4 years", "at least 2 years"
        min_experience_matches = re.finditer(r'(?:minimum|min|at least)\s*(\d+)\s*(?:years?|yrs?)', normalized_text)
        for match in min_experience_matches:
            extracted_minimum_experience_requirements.append(int(match.group(1)))

        # Clean text to avoid double counting ranges in the general pattern check
        cleaned_job_description = re.sub(r'\d+\s*(?:-|to|–)\s*\d+\s*(?:years?|yrs?)', '', normalized_text)
        cleaned_job_description = re.sub(r'\d+\s*\+\s*(?:years?|yrs?)', '', cleaned_job_description)
        cleaned_job_description = re.sub(r'(?:minimum|min|at least)\s*\d+\s*(?:years?|yrs?)', '', cleaned_job_description)
        
        # 4. General "{number} years" near "experience"
        general_experience_matches = re.finditer(r'(\d+)\s*(?:years?|yrs?)(?:.{0,30})?(?:experience|exp)', cleaned_job_description)
        for match in general_experience_matches:
            extracted_minimum_experience_requirements.append(int(match.group(1)))
            
        if not extracted_minimum_experience_requirements:
            # Experience requirement unspecified, assume qualified
            return True
            
        # Accept if the lowest entry threshold found is <= candidate's max experience limit
        lowest_required_experience = min(extracted_minimum_experience_requirements)
        return lowest_required_experience <= self.max_years_of_experience

    # Backward compatibility alias
    evaluate = is_candidate_qualified

# Backward compatibility alias
YOEFilter = YearsOfExperienceFilter

if __name__ == "__main__":
    filter_instance = YearsOfExperienceFilter(2)
    assert filter_instance.is_candidate_qualified("We are looking for someone with 0-2 years of experience.") is True
    assert filter_instance.is_candidate_qualified("Need 1-3 years in React") is True
    assert filter_instance.is_candidate_qualified("Requires 3-5 years of experience") is False
    assert filter_instance.is_candidate_qualified("3+ years of experience needed") is False
    assert filter_instance.is_candidate_qualified("Minimum 4 years required") is False
    assert filter_instance.is_candidate_qualified("05 years of experience") is False
    print("All YearsOfExperienceFilter assertions passed.")
