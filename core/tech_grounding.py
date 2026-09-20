"""
Strict Anti-Hallucination Grounding Validator for Tech Stack Extraction.
Guarantees that NO technology is ever reported unless it is explicitly present
as a physical token/string in the job text. Returns empty list if not mentioned.
"""

import re
from typing import List, Optional, Set
from core.tech_taxonomy import TECH_TAXONOMY, ALIAS_TO_CANONICAL, get_canonical_tech

# Ambiguous tokens requiring strict contextual disambiguation
AMBIGUOUS_TECH = {"c", "r", "go", "rust", "cv", "next"}

DISAMBIGUATION_PATTERNS = {
    "go": re.compile(r'\b(?:golang|go\s+(?:language|programming|backend|developer|engineer|code)|(?:python|java|c\+\+|rust|node)[\s,/]+go[\s,/]+(?:python|java|c\+\+|rust|node)?)\b', re.IGNORECASE),
    "rust": re.compile(r'\b(?:rustlang|rust\s+(?:lang|language|developer|engineer|programming)|(?:c\+\+|go|python)[\s,/]+rust)\b', re.IGNORECASE),
    "c": re.compile(r'\b(?:c\s+(?:language|programming)|c\s*\/\s*c\+\+|c\s*,\s*c\+\+|ansi\s*c|embedded\s+c)\b', re.IGNORECASE),
    "r": re.compile(r'\b(?:r\s+(?:programming|language|stats?|scripting)|(?:python|sql)[\s,/]+r[\s,/]+(?:python|sql)?)\b', re.IGNORECASE),
    "cv": re.compile(r'\b(?:computer\s+vision|cv\s+algorithms?|deep\s+learning\s+and\s+cv)\b', re.IGNORECASE),
}

# Compiled regex cache for aliases to maximize runtime throughput
_ALIAS_REGEX_CACHE = {}

def _get_alias_regex(alias: str) -> re.Pattern:
    if alias not in _ALIAS_REGEX_CACHE:
        # Escape special regex chars like ++ or # or .
        escaped = re.escape(alias)
        # Word boundary: for tokens ending in +, # or word chars
        if alias.endswith('+') or alias.endswith('#'):
            pattern = rf'(?<!\w){escaped}(?!\w)'
        else:
            pattern = rf'\b{escaped}\b'
        _ALIAS_REGEX_CACHE[alias] = re.compile(pattern, re.IGNORECASE)
    return _ALIAS_REGEX_CACHE[alias]


def is_tech_grounded_in_text(canonical_tech: str, text: str) -> bool:
    """
    Verifies with 100% mathematical certainty whether a given technology or any
    of its registered canonical aliases physically appears in the text.
    Rejects hallucinations.
    """
    if not text or not canonical_tech:
        return False

    meta = TECH_TAXONOMY.get(canonical_tech)
    if not meta:
        # If not in taxonomy, test exact word boundary match of the name itself
        escaped = re.escape(canonical_tech.lower())
        return bool(re.search(rf'\b{escaped}\b', text, re.IGNORECASE))

    # Check disambiguation rules for single letters or dual-meaning English words
    tech_lower = canonical_tech.lower()
    if tech_lower in AMBIGUOUS_TECH:
        pattern = DISAMBIGUATION_PATTERNS.get(tech_lower)
        if pattern:
            return bool(pattern.search(text))

    # Check canonical name
    can_regex = _get_alias_regex(canonical_tech)
    if can_regex.search(text):
        return True

    # Check all registered aliases
    for alias in meta["aliases"]:
        if alias.lower() in AMBIGUOUS_TECH:
            pat = DISAMBIGUATION_PATTERNS.get(alias.lower())
            if pat and pat.search(text):
                return True
        else:
            regex = _get_alias_regex(alias)
            if regex.search(text):
                return True

    return False


def validate_and_filter_tech_stack(candidate_skills: List[str], text: str) -> List[str]:
    """
    Takes candidate skills (e.g. proposed by an LLM) and prunes any skill
    that cannot be proven to exist in the job description.
    Returns sorted, deduplicated canonical names.
    If no valid skills remain, returns [].
    """
    if not candidate_skills or not text:
        return []

    grounded: Set[str] = set()
    for raw_skill in candidate_skills:
        if not raw_skill or not isinstance(raw_skill, str):
            continue
        cleaned = raw_skill.strip()
        canonical = get_canonical_tech(cleaned) or cleaned

        # Grounding check: must be physically verifiable in text
        if is_tech_grounded_in_text(canonical, text):
            grounded.add(canonical)

    return sorted(list(grounded))


def extract_deterministic_tech_stack(text: str) -> List[str]:
    """
    Deterministically scans text against the master taxonomy with zero LLM cost.
    Guarantees zero hallucination.
    Returns [] if no tech stack is mentioned.
    """
    if not text:
        return []

    found: Set[str] = set()
    for canonical, meta in TECH_TAXONOMY.items():
        if is_tech_grounded_in_text(canonical, text):
            found.add(canonical)

    return sorted(list(found))
