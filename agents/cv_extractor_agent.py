# agents/cv_extractor_agent.py
import sys
import os
from pathlib import Path
import json

# --- Add project root to sys.path ---
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

from utils.llm_utils import generate_structured_output
from utils.database_utils import update_candidate_extraction, get_db_connection # Add function to get CV text later
from utils.config_loader import load_config

# Load config to get prompt path (if using external prompts)
try:
    config = load_config()
    prompt_path_cv = project_root / "prompts" / "cv_extraction_prompt.txt"
    if prompt_path_cv.is_file():
        with open(prompt_path_cv, 'r') as f:
            CV_EXTRACTION_PROMPT_TEMPLATE = f.read()
        print("Loaded CV extraction prompt from file.")
    else:
         print("CV extraction prompt file not found. Using default inline prompt.")
         CV_EXTRACTION_PROMPT_TEMPLATE = """
Analyze the following CV text and extract professional information into a JSON object.
Focus on skills, total years of relevant experience, highest education level, and recent job titles.
The JSON object should have keys like "skills", "total_experience_years", "education", "recent_job_titles".

CV Text:
---
{cv_text}
---

Respond ONLY with the valid JSON object. Do not include explanations or introductory text.
"""
except Exception as e:
    print(f"Error loading config or CV prompt: {e}. Using fallback prompt.")
    CV_EXTRACTION_PROMPT_TEMPLATE = """
Analyze the following CV text and extract professional information into a JSON object.
Focus on skills, total years of relevant experience, highest education level, and recent job titles.
The JSON object should have keys like "skills", "total_experience_years", "education", "recent_job_titles".

CV Text:
---
{cv_text}
---

Respond ONLY with the valid JSON object. Do not include explanations or introductory text.
"""

def validate_and_clean_cv_data(cv_data: dict) -> dict:
    """Validates and cleans the LLM-generated CV data."""
    if not isinstance(cv_data, dict):
        return {}
        
    cleaned = {}
    
    # Clean technical skills
    skills = cv_data.get('skills', [])
    if isinstance(skills, list):
        cleaned['skills'] = [
            str(s).lower().strip() 
            for s in skills 
            if s and isinstance(s, (str, int, float))
        ]
    else:
        cleaned['skills'] = []
        
    # Clean soft skills
    soft_skills = cv_data.get('soft_skills', [])
    if isinstance(soft_skills, list):
        cleaned['soft_skills'] = [
            str(s).lower().strip() 
            for s in soft_skills 
            if s and isinstance(s, str)
        ]
    else:
        cleaned['soft_skills'] = []
        
    # Clean domain expertise
    domain = cv_data.get('domain_expertise', [])
    if isinstance(domain, list):
        cleaned['domain_expertise'] = [
            str(d).lower().strip() 
            for d in domain 
            if d and isinstance(d, str)
        ]
    else:
        cleaned['domain_expertise'] = []
        
    # Clean total experience years
    exp_years = cv_data.get('total_experience_years')
    if isinstance(exp_years, (int, float)):
        cleaned['total_experience_years'] = float(exp_years)
    elif isinstance(exp_years, str):
        # Try to extract first number from string
        import re
        numbers = re.findall(r'\d+\.?\d*', exp_years)
        if numbers:
            try:
                cleaned['total_experience_years'] = float(numbers[0])
            except ValueError:
                cleaned['total_experience_years'] = None
        else:
            cleaned['total_experience_years'] = None
    else:
        cleaned['total_experience_years'] = None
        
    # Clean education list
    edu = cv_data.get('education', [])
    if isinstance(edu, list):
        cleaned['education'] = [
            str(e).strip() 
            for e in edu 
            if e and isinstance(e, str)
        ]
    else:
        cleaned['education'] = []
        
    # Clean certifications
    certs = cv_data.get('certifications', [])
    if isinstance(certs, list):
        cleaned['certifications'] = [
            str(c).lower().strip() 
            for c in certs 
            if c and isinstance(c, str)
        ]
    else:
        cleaned['certifications'] = []
        
    # Clean recent job titles
    titles = cv_data.get('recent_job_titles', [])
    if isinstance(titles, list):
        cleaned['recent_job_titles'] = [
            str(t).strip() 
            for t in titles 
            if t and isinstance(t, str)
        ][:2]  # Keep only most recent 2
    else:
        cleaned['recent_job_titles'] = []
        
    # Clean industry experience
    industry = cv_data.get('industry_experience', [])
    if isinstance(industry, list):
        cleaned['industry_experience'] = [
            str(i).lower().strip() 
            for i in industry 
            if i and isinstance(i, str)
        ]
    else:
        cleaned['industry_experience'] = []
        
    return cleaned

def extract_cv_data(candidate_id: int, cv_text: str) -> dict | None:
    """
    Uses the LLM to extract structured data from CV text.

    Args:
        candidate_id: The database ID of the candidate.
        cv_text: The full text extracted from the candidate's CV PDF.

    Returns:
        The extracted data as a dictionary, or None if extraction fails.
    """
    print(f"\nAttempting to extract data from CV for Candidate ID: {candidate_id}...")

    if not cv_text or len(cv_text) < 50: # Basic check for meaningful content
        print(f"Error: CV text for Candidate ID {candidate_id} is empty or too short.")
        # Consider logging the filename associated with this ID if possible
        return None

    # Limit CV text length if necessary (Ollama models have context limits)
    # Find your model's limit. Mistral 7B is often around 4k-8k tokens.
    # A simple character limit might be sufficient for now.
    MAX_CV_CHARS = 15000 # ~4k tokens, adjust as needed
    if len(cv_text) > MAX_CV_CHARS:
        print(f"Warning: CV text for Candidate {candidate_id} truncated to {MAX_CV_CHARS} chars.")
        cv_text = cv_text[:MAX_CV_CHARS]


    prompt = CV_EXTRACTION_PROMPT_TEMPLATE.format(cv_text=cv_text)

    # Define a system message
    system_message = "You are an AI assistant specialized in parsing CVs/resumes. Respond ONLY with the required JSON object containing extracted professional information like skills, experience, and education. No explanations."

    extracted_data_json = generate_structured_output(prompt, system_message=system_message)

    if extracted_data_json and isinstance(extracted_data_json, dict):
        # Validate and clean the data
        cleaned_data = validate_and_clean_cv_data(extracted_data_json)
        print(f"Successfully extracted and cleaned data for Candidate ID: {candidate_id}")
        print("Cleaned Data:")
        print(json.dumps(cleaned_data, indent=2))
        return cleaned_data
    else:
        print(f"Failed to generate valid structured data for Candidate ID: {candidate_id}")
        # Log the CV filename if possible for debugging
        return None

# --- Example Usage (for testing this agent) ---
if __name__ == '__main__':
    print("--- Testing CV Extractor Agent ---")
    # This test requires the database to be set up and have at least one candidate
    try:
        config = load_config()
        db_path = config['database_path']
        conn = get_db_connection(db_path)

        # Fetch a sample Candidate to test (e.g., the first one)
        cursor = conn.cursor()
        # Fetch candidate with non-null text
        cursor.execute("SELECT candidate_id, cv_text, cv_filename FROM candidates WHERE cv_text IS NOT NULL AND LENGTH(cv_text) > 0 LIMIT 1")
        candidate_row = cursor.fetchone()

        if candidate_row:
            test_cand_id = candidate_row['candidate_id']
            test_cv_text = candidate_row['cv_text']
            test_cv_filename = candidate_row['cv_filename']
            print(f"Testing with Candidate ID: {test_cand_id} (Filename: {test_cv_filename})")

            extracted_data = extract_cv_data(test_cand_id, test_cv_text)

            if extracted_data:
                print("\nExtracted Data:")
                print(json.dumps(extracted_data, indent=2))

                # Try saving it back to the database
                success = update_candidate_extraction(conn, test_cand_id, extracted_data)
                if success:
                    print(f"\nSuccessfully updated extracted data in DB for Candidate ID: {test_cand_id}")
                else:
                    print(f"\nFailed to update extracted data in DB for Candidate ID: {test_cand_id}")
            else:
                print("\nCV data extraction failed.")

        else:
            print("No candidates with extracted text found in the database to test.")

        conn.close()

    except Exception as e:
        print(f"\nAn error occurred during CV Extractor test: {e}")
        if 'conn' in locals() and conn:
             conn.close()