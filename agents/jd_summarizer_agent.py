# agents/jd_summarizer_agent.py
import sys
import os
from pathlib import Path
import json

# --- Add project root to sys.path ---
# This is one way to handle imports when potentially running scripts directly
# or when modules are nested. Adjust the number of .parent calls as needed
# based on where you run the script from. Ideally, run from root.
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

from utils.llm_utils import generate_structured_output
from utils.database_utils import update_jd_summary, get_db_connection # Add function to get JD text later
from utils.config_loader import load_config

# Load config to get prompt path (if using external prompts)
try:
    config = load_config()
    # Construct prompt path relative to project root potentially
    prompt_path_jd = project_root / "prompts" / "jd_summary_prompt.txt"
    if prompt_path_jd.is_file():
        with open(prompt_path_jd, 'r') as f:
            JD_SUMMARY_PROMPT_TEMPLATE = f.read()
        print("Loaded JD summary prompt from file.")
    else:
         print("JD summary prompt file not found. Using default inline prompt.")
         # Define a default inline prompt if the file isn't found
         JD_SUMMARY_PROMPT_TEMPLATE = """
Analyze the following job description and extract the key information into a JSON object.
The JSON object should have keys like "required_skills", "preferred_skills", "required_experience_years", "required_education", "key_responsibilities".

Job Description:
---
{job_description_text}
---

Respond ONLY with the valid JSON object.
"""
except Exception as e:
    print(f"Error loading config or JD prompt: {e}. Using fallback prompt.")
    # Fallback inline prompt in case of any error
    JD_SUMMARY_PROMPT_TEMPLATE = """
Analyze the following job description and extract the key information into a JSON object.
The JSON object should have keys like "required_skills", "preferred_skills", "required_experience_years", "required_education", "key_responsibilities".

Job Description:
---
{job_description_text}
---

Respond ONLY with the valid JSON object.
"""


def validate_and_clean_summary(summary_data: dict) -> dict:
    """Validates and cleans the LLM-generated summary data."""
    if not isinstance(summary_data, dict):
        return {}
        
    cleaned = {}
    
    # Clean required skills
    skills = summary_data.get('required_skills', [])
    if isinstance(skills, list):
        cleaned['required_skills'] = [
            str(s).lower().strip() 
            for s in skills 
            if s and isinstance(s, (str, int, float))
        ]
    else:
        cleaned['required_skills'] = []
        
    # Clean preferred skills
    pref_skills = summary_data.get('preferred_skills', [])
    if isinstance(pref_skills, list):
        cleaned['preferred_skills'] = [
            str(s).lower().strip() 
            for s in pref_skills 
            if s and isinstance(s, (str, int, float))
        ]
    else:
        cleaned['preferred_skills'] = []
        
    # Clean domain expertise
    domain = summary_data.get('domain_expertise', [])
    if isinstance(domain, list):
        cleaned['domain_expertise'] = [
            str(d).lower().strip() 
            for d in domain 
            if d and isinstance(d, str)
        ]
    else:
        cleaned['domain_expertise'] = []
        
    # Clean soft skills
    soft = summary_data.get('soft_skills', [])
    if isinstance(soft, list):
        cleaned['soft_skills'] = [
            str(s).lower().strip() 
            for s in soft 
            if s and isinstance(s, str)
        ]
    else:
        cleaned['soft_skills'] = []
        
    # Clean education requirement
    edu = summary_data.get('required_education')
    cleaned['required_education'] = str(edu).lower().strip() if edu else None
        
    # Clean experience requirement
    exp = summary_data.get('required_experience_years')
    cleaned['required_experience_years'] = str(exp).strip() if exp else None
        
    # Clean essential requirements
    reqs = summary_data.get('essential_requirements', [])
    if isinstance(reqs, list):
        cleaned['essential_requirements'] = [
            str(r).lower().strip() 
            for r in reqs 
            if r and isinstance(r, str)
        ]
    else:
        cleaned['essential_requirements'] = []
        
    # Clean responsibilities
    resp = summary_data.get('key_responsibilities', [])
    if isinstance(resp, list):
        cleaned['key_responsibilities'] = [
            str(r).strip() 
            for r in resp 
            if r and isinstance(r, str)
        ]
    else:
        cleaned['key_responsibilities'] = []
        
    return cleaned

def summarize_job_description(jd_id: int, job_description_text: str) -> dict | None:
    """
    Uses the LLM to summarize a job description into a structured format.

    Args:
        jd_id: The database ID of the job description.
        job_description_text: The full text of the job description.

    Returns:
        The structured summary as a dictionary, or None if summarization fails.
    """
    print(f"\nAttempting to summarize JD ID: {jd_id}...")

    if not job_description_text:
        print(f"Error: Job description text for JD ID {jd_id} is empty.")
        return None

    prompt = JD_SUMMARY_PROMPT_TEMPLATE.format(job_description_text=job_description_text)

    # Define a system message to reinforce JSON output
    system_message = "You are an AI assistant specialized in parsing job descriptions. Respond ONLY with the required JSON object, containing extracted information like skills, experience, education, and responsibilities. No explanations."

    summary_json = generate_structured_output(prompt, system_message=system_message)

    if summary_json and isinstance(summary_json, dict):
        # Validate and clean the data
        cleaned_summary = validate_and_clean_summary(summary_json)
        print(f"Successfully generated and cleaned summary for JD ID: {jd_id}")
        print("Cleaned Summary:")
        print(json.dumps(cleaned_summary, indent=2))
        return cleaned_summary
    else:
        print(f"Failed to generate valid structured summary for JD ID: {jd_id}")
        return None

# --- Example Usage (for testing this agent) ---
if __name__ == '__main__':
    print("--- Testing JD Summarizer Agent ---")
    # This test requires the database to be set up and have at least one JD
    try:
        config = load_config()
        db_path = config['database_path']
        conn = get_db_connection(db_path)

        # Fetch a sample JD to test (e.g., the first one)
        cursor = conn.cursor()
        cursor.execute("SELECT jd_id, original_description FROM job_descriptions LIMIT 1")
        jd_row = cursor.fetchone()

        if jd_row:
            test_jd_id = jd_row['jd_id']
            test_jd_text = jd_row['original_description']
            print(f"Testing with JD ID: {test_jd_id}")

            summary = summarize_job_description(test_jd_id, test_jd_text)

            if summary:
                print("\nGenerated Summary:")
                print(json.dumps(summary, indent=2))

                # Try saving it back to the database
                success = update_jd_summary(conn, test_jd_id, summary)
                if success:
                    print(f"\nSuccessfully updated summary in DB for JD ID: {test_jd_id}")
                else:
                    print(f"\nFailed to update summary in DB for JD ID: {test_jd_id}")
            else:
                print("\nSummary generation failed.")

        else:
            print("No job descriptions found in the database to test.")

        conn.close()

    except Exception as e:
        print(f"\nAn error occurred during JD Summarizer test: {e}")
        # Ensure connection is closed if it exists
        if 'conn' in locals() and conn:
             conn.close()