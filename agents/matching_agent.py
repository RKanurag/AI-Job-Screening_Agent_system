
import sys
from pathlib import Path
import json
import re
import sqlite3
import logging

# --- Add project root to sys.path ---
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

# Use absolute imports for clarity when running scripts directly
try:
    from utils.database_utils import get_jd, get_candidate, add_or_update_match, get_db_connection
    from utils.config_loader import load_config
except ImportError as e:
    print(f"Error importing utils: {e}. Ensure script is run from project root or utils are in PYTHONPATH.")
    sys.exit(1)


# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


# --- Load Config ---
try:
    config = load_config()
    DEFAULT_WEIGHTS = {'skills': 0.4, 'experience': 0.25, 'education': 0.25, 'requirements': 0.1}
    MATCHING_WEIGHTS = config.get('matching_weights', DEFAULT_WEIGHTS)
    if not isinstance(MATCHING_WEIGHTS, dict):
        logging.warning(f"Invalid 'matching_weights' format in config. Using defaults: {DEFAULT_WEIGHTS}")
        MATCHING_WEIGHTS = DEFAULT_WEIGHTS
    logging.info(f"Matching Agent using weights: {MATCHING_WEIGHTS}")
except Exception as e:
    logging.error(f"Error loading config: {e}. Using default weights: {DEFAULT_WEIGHTS}")
    MATCHING_WEIGHTS = DEFAULT_WEIGHTS


# --- Skill Synonym Dictionary ---
SKILL_SYNONYMS = {
    "databases": ["sql", "mysql", "postgresql", "nosql", "database management", "database"],
    "web development": ["html", "css", "javascript", "react", "angular", "vue", "node.js", "django", "flask", "spring boot", "web dev", "frontend", "backend"],
    "cloud": ["aws", "azure", "gcp", "google cloud", "amazon web services", "cloud computing"],
    "machine learning": ["ml", "deep learning", "tensorflow", "pytorch", "scikit-learn", "ai"],
    "artificial intelligence": ["ai", "ml", "deep learning", "nlp", "computer vision"],
    "cybersecurity": ["security", "network security", "penetration testing", "pen testing", "risk assessment", "vulnerability assessment", "infosec"],
    "python": ["python3"],
    "java": ["java se", "java ee"],
    # Add more mappings as needed based on JD/CV variations
}


# --- Helper Functions ---

def safe_json_loads(json_string: str | None) -> dict | list | None:
    """Safely loads a JSON string, returning None on error or if input is None/empty."""
    if not json_string:
        return None
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.warning(f"Could not decode JSON: {e} - Input starts with: {json_string[:100]}...")
        return None

def parse_experience_years(exp_string: str | None) -> float | None:
    """Attempts to parse minimum years of experience from a string."""
    if not exp_string or not isinstance(exp_string, str):
        return None
    numbers = re.findall(r'\d+\.?\d*', exp_string)
    if numbers:
        try:
            return float(numbers[0]) # Return the first number found (min in ranges)
        except ValueError:
            return None
    return None

def expand_skills(skill_set: set[str], synonyms: dict) -> set[str]:
    """Expands a set of skills using the synonym dictionary."""
    if not skill_set:
        return set()
    expanded = set(skill_set) # Start with original skills
    for skill in skill_set:
        # Check direct synonyms
        if skill in synonyms:
            expanded.update(synonyms[skill])
        # Check if skill is a synonym value for a broader category
        for key, value_list in synonyms.items():
            if skill in value_list:
                expanded.add(key) # Add the broader category too
    return expanded


# --- Core Matching Logic Functions ---

def calculate_skill_match(jd_data: dict, cv_data: dict) -> float:
    """
    Calculates skill match score considering categories and synonyms.
    Assumes input dictionaries contain cleaned data.
    """
    logging.debug("Calculating Skill Match Component...")

    # Get JD Skills (expecting cleaned lists)
    jd_req_skills_raw = set(jd_data.get('required_skills', []))
    jd_pref_skills_raw = set(jd_data.get('preferred_skills', []))
    jd_domain_raw = set(jd_data.get('domain_expertise', []))
    jd_soft_raw = set(jd_data.get('soft_skills', []))

    # --- Expand JD Skills using Synonyms ---
    jd_req_skills = expand_skills(jd_req_skills_raw, SKILL_SYNONYMS)
    jd_pref_skills = expand_skills(jd_pref_skills_raw, SKILL_SYNONYMS)
    jd_domain = expand_skills(jd_domain_raw, SKILL_SYNONYMS)
    # Soft skills usually don't need synonym expansion
    jd_soft = jd_soft_raw
    logging.debug(f"  JD Skills - Required(Raw:{len(jd_req_skills_raw)} Expanded:{len(jd_req_skills)}), Preferred(Raw:{len(jd_pref_skills_raw)} Expanded:{len(jd_pref_skills)}), Domain(Raw:{len(jd_domain_raw)} Expanded:{len(jd_domain)}), Soft({len(jd_soft)})")


    # Get CV Skills (expecting cleaned lists)
    cv_tech_skills = set(cv_data.get('skills', []))
    cv_domain = set(cv_data.get('domain_expertise', []))
    cv_soft = set(cv_data.get('soft_skills', []))
    # Combine all CV skills for broader matching against required/preferred
    all_cv_skills = cv_tech_skills.union(cv_domain).union(cv_soft) # Combine all for checking required/preferred
    logging.debug(f"  CV Skills - Technical({len(cv_tech_skills)}), Domain({len(cv_domain)}), Soft({len(cv_soft)}), All({len(all_cv_skills)})")


    # --- Calculate matches ---

    # Required Skills Match (Compare Expanded JD Required vs ALL CV Skills)
    if jd_req_skills_raw: # Base score on original requirements count
        req_intersection = jd_req_skills.intersection(all_cv_skills)
        required_match = len(req_intersection) / len(jd_req_skills_raw)
        logging.debug(f"    Required Skills Match: {len(req_intersection)}/{len(jd_req_skills_raw)} = {required_match:.3f}")
    else:
        required_match = 0.5 # Neutral if JD requires none
        logging.debug(f"    Required Skills Match: N/A (JD requires none) -> Score: {required_match:.3f}")

    # Preferred Skills Match (Compare Expanded JD Preferred vs ALL CV Skills) - Bonus points
    if jd_pref_skills_raw:
        pref_intersection = jd_pref_skills.intersection(all_cv_skills)
        preferred_match = len(pref_intersection) / len(jd_pref_skills_raw) # Score based on fulfilling preferred
        logging.debug(f"    Preferred Skills Match: {len(pref_intersection)}/{len(jd_pref_skills_raw)} = {preferred_match:.3f}")
    else:
        preferred_match = 0.0 # No bonus if JD lists none
        logging.debug(f"    Preferred Skills Match: N/A (JD lists none) -> Score: {preferred_match:.3f}")

    # Domain Expertise Match (Compare Expanded JD Domain vs CV Domain)
    if jd_domain_raw:
        domain_intersection = jd_domain.intersection(cv_domain) # Match specific domain lists
        domain_match = len(domain_intersection) / len(jd_domain_raw)
        logging.debug(f"    Domain Expertise Match: {len(domain_intersection)}/{len(jd_domain_raw)} = {domain_match:.3f}")
    else:
        domain_match = 0.5 # Neutral if JD requires none
        logging.debug(f"    Domain Expertise Match: N/A (JD requires none) -> Score: {domain_match:.3f}")

    # Soft Skills Match (Compare JD Soft vs CV Soft)
    if jd_soft_raw:
        soft_intersection = jd_soft.intersection(cv_soft) # Match specific soft skill lists
        soft_match = len(soft_intersection) / len(jd_soft_raw)
        logging.debug(f"    Soft Skills Match: {len(soft_intersection)}/{len(jd_soft_raw)} = {soft_match:.3f}")
    else:
        soft_match = 0.5 # Neutral if JD requires none
        logging.debug(f"    Soft Skills Match: N/A (JD requires none) -> Score: {soft_match:.3f}")


    # Weight the different skill categories
    skill_weights = { 'required': 0.60, 'preferred': 0.10, 'domain': 0.15, 'soft': 0.15 }
    total_weight = 0
    weighted_score = 0

    if jd_req_skills_raw:
        weighted_score += required_match * skill_weights['required']
        total_weight += skill_weights['required']
    if jd_pref_skills_raw:
        weighted_score += preferred_match * skill_weights['preferred']
        total_weight += skill_weights['preferred']
    if jd_domain_raw:
        weighted_score += domain_match * skill_weights['domain']
        total_weight += skill_weights['domain']
    if jd_soft_raw:
         weighted_score += soft_match * skill_weights['soft']
         total_weight += skill_weights['soft']

    # If no skills categories listed at all in JD, return neutral 0.5
    if total_weight == 0:
        logging.debug("  Skill Match Final - No skill categories listed in JD. Returning neutral 0.5")
        return 0.5

    # Normalize score based on the weights actually used
    final_skill_score = weighted_score / total_weight
    logging.debug(f"  Skill Match Final Weighted Score: {final_skill_score:.3f}")

    return final_skill_score


def check_essential_requirements(jd_data: dict, cv_data: dict) -> float:
    """Checks if candidate meets essential requirements (e.g., certifications)."""
    logging.debug("Checking Essential Requirements...")
    # Expect cleaned list from JD summary
    essential_reqs = set(jd_data.get('essential_requirements', []))
    logging.debug(f"  JD Essential Reqs: {essential_reqs}")

    if not essential_reqs:
        logging.debug("  No essential requirements specified by JD. Score: 1.0")
        return 1.0

    # Get cleaned data from CV
    cv_skills = set(cv_data.get('skills', []))
    cv_certs = set(cv_data.get('certifications', []))
    cv_education_list = cv_data.get('education', [])
    # Combine CV skills and certs directly
    cv_quals_combined = cv_skills.union(cv_certs)
    # Create a string of CV education to check for substrings
    cv_edu_text = " ".join(str(e).lower() for e in cv_education_list)

    logging.debug(f"  CV Quals - Skills({len(cv_skills)}), Certs({len(cv_certs)}), Edu Text: {cv_edu_text[:50]}...")

    met_requirements = 0
    for req in essential_reqs:
        req_lower = req.lower() # Ensure requirement is lowercase for comparison
        # Check exact match in combined skills/certs OR substring match in education string
        if req_lower in cv_quals_combined or req_lower in cv_edu_text:
            met_requirements += 1
            logging.debug(f"    Requirement '{req_lower}' MET.")
        else:
             logging.debug(f"    Requirement '{req_lower}' NOT MET.")

    score = met_requirements / len(essential_reqs) if essential_reqs else 1.0
    logging.debug(f"  Essential Requirements Score: {met_requirements}/{len(essential_reqs)} = {score:.3f}")
    return score


def calculate_education_match(jd_education_str: str | None, cv_education_list: list | None) -> float:
    """Enhanced education matching with degree level hierarchy and stricter logic."""
    logging.debug("Calculating Education Match...")
    if not jd_education_str or not isinstance(jd_education_str, str) or jd_education_str.lower() in ['none', 'none specified', 'n/a']:
        logging.debug("  JD Education not specified or invalid. Score: 0.5 (Neutral)")
        return 0.5
    # Expect cleaned list from CV data
    if not cv_education_list or not isinstance(cv_education_list, list):
         logging.debug("  CV Education list is empty or invalid. Score: 0.0")
         return 0.0

    degree_hierarchy = {
        'phd': 4, 'doctorate': 4,
        'master': 3, 'mba': 3, 'msc': 3, 'meng': 3, 'm.sc': 3, 'm.eng': 3, # Added common Master variations
        'bachelor': 2, 'undergraduate': 2, 'bs': 2, 'ba': 2, 'beng': 2, 'b.s': 2, 'b.a': 2, 'b.eng': 2, # Added abbreviations
        'associate': 1, 'diploma': 1, 'certificate': 1 # Treat certs/diplomas as lower level
    }

    # Get required level from JD string
    jd_level = 0
    jd_edu_lower = jd_education_str.lower()
    for degree, level in degree_hierarchy.items():
        if degree in jd_edu_lower:
            jd_level = max(jd_level, level)
    logging.debug(f"  JD Required Edu Level: {jd_level} (from '{jd_education_str}')")
    # If JD requirement is vague but non-empty (e.g., "related field")
    if jd_level == 0 and len(jd_edu_lower) > 3:
        logging.debug("  JD Edu requirement not recognized as specific level. Score: 0.5 (Neutral)")
        return 0.5
    elif jd_level == 0: # If JD req is truly empty/unparseable after cleaning
         logging.debug("  JD Edu requirement effectively empty. Score: 0.5 (Neutral)")
         return 0.5


    # Get highest candidate level from CV list
    cv_level = 0
    highest_cv_edu_str = ""
    for edu_str in cv_education_list:
        edu_lower = str(edu_str).lower() # Should already be lowercase from cleaning
        for degree, level in degree_hierarchy.items():
            if degree in edu_lower:
                if level > cv_level:
                    cv_level = level
                    highest_cv_edu_str = edu_str # Store the string that gave the highest level
    logging.debug(f"  CV Highest Edu Level: {cv_level} (from '{highest_cv_edu_str}' in {cv_education_list})")

    # Compare levels
    if cv_level >= jd_level:
        logging.debug("  Education Score: 1.0 (CV meets or exceeds requirement)")
        return 1.0
    # Removed partial credit for lower level - requires meeting the bar
    else: # CV level is < JD level OR CV level is 0
        logging.debug(f"  Education Score: 0.0 (CV level {cv_level} < JD level {jd_level} or CV level is 0)")
        return 0.0


def calculate_experience_match(jd_exp_years_str: str | None, cv_total_exp_years: float | int | None) -> float:
    """Calculates an experience match score with graduated scoring."""
    logging.debug("Calculating Experience Match...")
    jd_min_years = parse_experience_years(jd_exp_years_str)
    logging.debug(f"  JD Min Years Required: {jd_min_years} (from '{jd_exp_years_str}')")

    # Handle case where JD doesn't specify years
    if jd_min_years is None:
        if cv_total_exp_years is not None and isinstance(cv_total_exp_years, (int, float)) and cv_total_exp_years > 0:
             logging.debug("  JD experience not specified, CV has experience. Score: 0.5 (Neutral)")
             return 0.5
        else:
             logging.debug("  JD experience not specified, CV lacks experience. Score: 0.0")
             return 0.0

    # Handle case where CV doesn't specify years
    if cv_total_exp_years is None or not isinstance(cv_total_exp_years, (int, float)) or cv_total_exp_years < 0: # Allow 0 years
        logging.debug("  CV experience not available or not numeric/positive. Score: 0.0")
        return 0.0

    logging.debug(f"  CV Total Experience Years: {cv_total_exp_years}")

    # Calculate score based on ratio and potential bonus
    if cv_total_exp_years >= jd_min_years:
        # Bonus for exceeding requirement (e.g., +0.05 per year over min, capped at +0.2)
        bonus = min(0.2, (cv_total_exp_years - jd_min_years) * 0.05)
        score = min(1.0, 1.0 + bonus) # Keep score capped at 1.0 for simplicity now
        logging.debug(f"  Experience Score: {score:.3f} (CV meets/exceeds requirement)")
        return score
    else:
        # Partial score based on ratio if below requirement
        partial_score = cv_total_exp_years / jd_min_years
        logging.debug(f"  Experience Score: {partial_score:.3f} (CV below requirement, partial score)")
        return max(0.0, partial_score) # Ensure score is not negative


# --- Main Scoring Function ---

def calculate_match_score(jd_id: int, candidate_id: int, conn: sqlite3.Connection) -> tuple[float | None, dict | None]:
    """
    Calculates the overall match score between a JD and a candidate using enhanced logic.
    Retrieves data, validates JSON, calls component scoring functions, and applies weights.
    """
    logging.info(f"--- Calculating match score: JD {jd_id} vs Candidate {candidate_id} ---")

    # 1. Retrieve data from DB
    jd_row = get_jd(conn, jd_id)
    candidate_row = get_candidate(conn, candidate_id)

    if not jd_row or not candidate_row:
        logging.error(f"Missing JD ({jd_id}) or Candidate ({candidate_id}) database row.")
        return None, {"error": "Missing DB row data"}

    # 2. Safely load JSON data (expects cleaned data from agents)
    jd_data = safe_json_loads(jd_row['summary_json'])
    cv_data = safe_json_loads(candidate_row['extracted_data_json'])

    # 3. Validate JSON structure
    if not isinstance(jd_data, dict) or not isinstance(cv_data, dict):
        logging.error(f"Invalid or missing JSON data structure for JD {jd_id} or Cand {candidate_id}")
        error_detail = {}
        if not isinstance(jd_data, dict): error_detail["jd_error"] = f"Invalid JD JSON (Type: {type(jd_data).__name__})"
        if not isinstance(cv_data, dict): error_detail["cv_error"] = f"Invalid CV JSON (Type: {type(cv_data).__name__})"
        return 0.0, {"error": "Invalid JSON data structure", **error_detail}
    logging.debug(f"Successfully loaded JSON for JD {jd_id} and Candidate {candidate_id}")

    # 4. Calculate individual component scores
    skill_score = calculate_skill_match(jd_data, cv_data)
    experience_score = calculate_experience_match(
        jd_data.get('required_experience_years'),
        cv_data.get('total_experience_years')
    )
    education_score = calculate_education_match(
        jd_data.get('required_education'),
        cv_data.get('education', [])
    )
    requirements_score = check_essential_requirements(jd_data, cv_data)

    # 5. Apply weights from config
    weights = MATCHING_WEIGHTS
    overall_score = (
        skill_score * weights.get('skills', 0.4) +
        experience_score * weights.get('experience', 0.25) +
        education_score * weights.get('education', 0.25) +
        requirements_score * weights.get('requirements', 0.1)
    )
    overall_score = max(0.0, min(1.0, overall_score)) # Ensure 0-1 range

    # 6. Store details
    match_details = {
        "skills_score": round(skill_score, 3),
        "experience_score": round(experience_score, 3),
        "education_score": round(education_score, 3),
        "requirements_score": round(requirements_score, 3),
        "weights_used": weights
    }
    logging.info(f"Calculated Score: {overall_score:.3f} (JD {jd_id} vs Candidate {candidate_id})")

    return overall_score, match_details


# --- Test Execution Block ---
if __name__ == '__main__':
    print("\n--- Testing Matching Agent (Single Pair) ---")
    logging.getLogger().setLevel(logging.DEBUG) # Set log level for detailed test output

    try:
        config = load_config()
        db_path = config['database_path']
        conn = get_db_connection(db_path)

        # --- Specify IDs to Test ---
        test_jd_id = 1 # Example: Software Engineer JD
        # !!! IMPORTANT: Verify the actual candidate_id for C1164.pdf in your DB !!!
        # Use DB Browser for SQLite: SELECT candidate_id FROM candidates WHERE cv_filename = 'C1164.pdf';
        # Replace '184' below with the correct ID found.
        test_candidate_id = 4 # <<< SET CORRECT ID FOR C1164.pdf HERE >>>
        if test_candidate_id is None: # Basic check if you forget to set it
             print("\nERROR: Please set the correct 'test_candidate_id' for C1164.pdf in the script.\n")
             sys.exit(1)

        print(f"\nCalculating specific match for JD ID: {test_jd_id} and Candidate ID: {test_candidate_id} (Expected: C1164.pdf)")

        # Check if data exists first
        jd_check = get_jd(conn, test_jd_id)
        cand_check = get_candidate(conn, test_candidate_id)

        if jd_check and jd_check['summary_json'] and cand_check and cand_check['extracted_data_json']:
            print("--- Found JD and Candidate data, proceeding with score calculation ---")
            score, details = calculate_match_score(test_jd_id, test_candidate_id, conn)

            if score is not None:
                print(f"\nFINAL MATCH SCORE: {score:.3f}")
                print("--- MATCH DETAILS ---")
                print(json.dumps(details, indent=2))
                print("--------------------")

                # Save the match to the database
                success = add_or_update_match(conn, test_jd_id, test_candidate_id, score, details)
                if success:
                    # Update shortlist status if score meets threshold
                    threshold = config.get('shortlisting_threshold', 0.66)
                    if score >= threshold:
                        conn.execute(
                            "UPDATE matches SET shortlist_status = 1 WHERE jd_id = ? AND candidate_id = ?",
                            (test_jd_id, test_candidate_id)
                        )
                        conn.commit()
                        print(f"\nSuccessfully saved match and shortlisted candidate (Score: {score:.3f} >= {threshold})")
                    else:
                        print(f"\nSuccessfully saved match but candidate not shortlisted (Score: {score:.3f} < {threshold})")
                else:
                    print(f"\nFailed to save match for JD {test_jd_id} and Candidate {test_candidate_id}.")
            else:
                print(f"\nMatch score calculation returned None for JD {test_jd_id} and Candidate {test_candidate_id}.")
                print(f"Details returned: {details}") # Print details even if score is None
        else:
            print(f"\nCould not test JD {test_jd_id} and Candidate {test_candidate_id}. Missing data in DB.")
            if not jd_check: print("-> JD row missing.")
            elif not jd_check['summary_json']: print("-> JD summary JSON missing or empty.")
            if not cand_check: print("-> Candidate row missing.")
            elif not cand_check['extracted_data_json']: print("-> Candidate extracted JSON missing or empty.")

        conn.close()
        print("\nDatabase connection closed.")

    except Exception as e:
        print(f"\nAn error occurred during Matching Agent test: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals() and conn:
             conn.close()