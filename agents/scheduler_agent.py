# agents/scheduler_agent.py
import sys
from pathlib import Path
import json
import sqlite3

# --- Add project root to sys.path ---
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

from utils.database_utils import get_db_connection, get_jd
# We need a function to get candidate details, let's add it to database_utils
from utils.database_utils import get_candidate # Assume this retrieves the candidate row
from utils.config_loader import load_config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Email Template ---
# Keep it simple for the hackathon. Could be loaded from a file.
EMAIL_TEMPLATE = """
Subject: Interview Request: {job_title} at [Your Company Name]

Dear {candidate_name},

Thank you for your interest in the {job_title} position at [Your Company Name].

Your qualifications and experience align well with what we are looking for, and we would like to invite you for an initial interview to discuss your background and the role further.

Please let us know your availability over the next few business days for a brief 30-minute call. We can be flexible with timing.

We look forward to hearing from you soon.

Best regards,

[Your Name/Hiring Team]
[Your Company Name]
"""

def extract_candidate_name(candidate_data_json: str | None) -> str:
    """Attempts to extract the candidate's name from the extracted JSON data."""
    if not candidate_data_json:
        return "Candidate" # Default fallback
    try:
        data = json.loads(candidate_data_json)
        # Look for common name keys (adjust if your CV prompt extracts differently)
        name = data.get('name') or data.get('candidate_name') or data.get('full_name')
        return name if name else "Candidate"
    except (json.JSONDecodeError, AttributeError):
        logging.warning("Could not parse candidate JSON or find name field for email.")
        return "Candidate"

def generate_interview_requests(jd_id: int, shortlisted_candidates: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """
    Generates interview request email text for shortlisted candidates.

    Args:
        jd_id: The job description database ID.
        shortlisted_candidates: A list of dictionaries for shortlisted candidates
                               (must include 'candidate_id').
        conn: Active database connection.

    Returns:
        A list of dictionaries, each containing 'candidate_id', 'cv_filename',
        'email_subject', and 'email_body'.
    """
    logging.info(f"--- Generating interview requests for JD ID: {jd_id} ---")
    generated_emails = []

    # Get JD Title
    jd_row = get_jd(conn, jd_id)
    if not jd_row or not jd_row['title']:
        logging.error(f"Cannot generate emails: Job Title not found for JD ID {jd_id}")
        return []
    job_title = jd_row['title']

    for candidate_info in shortlisted_candidates:
        candidate_id = candidate_info.get('candidate_id')
        cv_filename = candidate_info.get('cv_filename', 'N/A') # Get filename if available

        if not candidate_id:
            logging.warning("Skipping candidate with missing ID in shortlist.")
            continue

        # Get Candidate Name from extracted data
        candidate_row = get_candidate(conn, candidate_id)
        if not candidate_row:
            logging.warning(f"Skipping email for Candidate ID {candidate_id}: Row not found.")
            continue

        candidate_name = extract_candidate_name(candidate_row['extracted_data_json'])

        # Format Email
        subject = f"Interview Request: {job_title} at [Your Company Name]"
        body = EMAIL_TEMPLATE.format(
            candidate_name=candidate_name,
            job_title=job_title
            # Add placeholders for [Your Company Name], [Your Name/Hiring Team]
        ).replace("[Your Company Name]", "Accenture").replace("[Your Name/Hiring Team]", "Accenture Hiring Team") # Quick replace for demo


        logging.info(f"  Generated email for Candidate {candidate_id} ({cv_filename})")
        generated_emails.append({
            "candidate_id": candidate_id,
            "cv_filename": cv_filename,
            "email_subject": subject,
            "email_body": body
        })

    logging.info(f"--- Finished generating {len(generated_emails)} interview requests for JD ID: {jd_id} ---")
    return generated_emails

# --- Example Usage (for testing this agent) ---
if __name__ == '__main__':
    print("--- Testing Scheduler Agent ---")
    try:
        config = load_config()
        db_path = config['database_path']
        conn = get_db_connection(db_path)

        # --- Find a JD with shortlisted candidates ---
        cursor = conn.cursor()
        # Find a JD ID that has matches with shortlist_status = 1
        cursor.execute("""
            SELECT DISTINCT m.jd_id
            FROM matches m
            WHERE m.shortlist_status = 1
            LIMIT 1
        """)
        jd_res = cursor.fetchone()

        if jd_res:
            test_jd_id = jd_res['jd_id']
            print(f"\nTesting email generation for JD ID: {test_jd_id}")

            # Get the shortlisted candidates for this JD (need info like ID and filename)
            # Re-run the shortlisting logic or query the matches table directly
            from agents.shortlisting_agent import shortlist_candidates_for_jd # Reuse for consistency
            # Note: shortlist_candidates_for_jd already updates status, maybe not ideal in test
            # Alternative: Query matches directly
            cursor.execute("""
                SELECT m.candidate_id, c.cv_filename, m.match_score
                FROM matches m
                JOIN candidates c ON m.candidate_id = c.candidate_id
                WHERE m.jd_id = ? AND m.shortlist_status = 1
            """, (test_jd_id,))
            shortlisted_rows = cursor.fetchall()

            if shortlisted_rows:
                 shortlisted_test_data = [dict(row) for row in shortlisted_rows] # Convert rows to dicts
                 print(f"Found {len(shortlisted_test_data)} shortlisted candidates for testing.")

                 emails = generate_interview_requests(test_jd_id, shortlisted_test_data, conn)

                 if emails:
                     print("\nGenerated Emails (showing first one):")
                     first_email = emails[0]
                     print(f"\n--- Email for Candidate ID: {first_email['candidate_id']} ({first_email['cv_filename']}) ---")
                     print(f"Subject: {first_email['email_subject']}")
                     print("--- Body ---")
                     print(first_email['email_body'])
                     print("------------")
                 else:
                     print("\nEmail generation failed.")
            else:
                 print(f"\nNo candidates found with shortlist_status=1 for JD ID {test_jd_id} in the database.")

        else:
            print("\nCould not find any job description with shortlisted candidates in the database.")
            print("Hint: Ensure main.py has run successfully and produced shortlisted candidates.")

        conn.close()

    except Exception as e:
        print(f"\nAn error occurred during Scheduler Agent test: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals() and conn:
             conn.close()