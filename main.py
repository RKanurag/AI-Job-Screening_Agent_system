# main.py
import sys
from pathlib import Path
import time
import sqlite3 # Import sqlite3 directly for type hinting if needed

# --- Add project root to sys.path ---
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

from utils.config_loader import load_config
from utils.database_utils import (
    get_db_connection, create_tables, add_job_description, add_candidate,
    get_all_jd_ids, get_all_candidate_ids, add_or_update_match, # Added necessary imports
    update_jd_summary, update_candidate_extraction, update_shortlist_status, get_matches_for_jd # Ensure all are imported
)
from utils.file_parsers import read_job_descriptions_from_csv, list_pdf_files, extract_text_from_pdf
from agents.jd_summarizer_agent import summarize_job_description
from agents.cv_extractor_agent import extract_cv_data
# +++ NEW IMPORTS +++
from agents.matching_agent import calculate_match_score
from agents.shortlisting_agent import shortlist_candidates_for_jd
# +++ END NEW IMPORTS +++


def process_job_descriptions(conn: sqlite3.Connection, jd_csv_path: str):
    """Reads JDs from CSV, adds to DB, and triggers summarization."""
    print("\n--- Processing Job Descriptions ---")
    try:
        jds_df = read_job_descriptions_from_csv(jd_csv_path)
    except (FileNotFoundError, ValueError, Exception) as e:
        print(f"Error reading or validating JD CSV: {e}. Skipping JD processing.")
        return

    processed_count = 0
    skipped_summary = 0
    for index, row in jds_df.iterrows():
        title = row.get('Job Title', 'N/A')
        description = row.get('Job Description', '')

        if not description:
             print(f"Skipping JD '{title}' due to missing description.")
             continue

        # Add JD to database
        jd_id = add_job_description(conn, title, description)
        if jd_id != -1:
             # --- Check if summary already exists (Optimization) ---
             cursor = conn.cursor()
             cursor.execute("SELECT summary_json FROM job_descriptions WHERE jd_id = ?", (jd_id,))
             existing_summary = cursor.fetchone()
             if existing_summary and existing_summary['summary_json']:
                  print(f"Skipping summarization for JD ID {jd_id}, summary already exists.")
                  skipped_summary += 1
                  processed_count += 1 # Still count as processed overall
                  continue
             # --- End Check ---

             # Trigger summarization agent
             summary = summarize_job_description(jd_id, description)
             if summary:
                 update_jd_summary(conn, jd_id, summary)
             processed_count += 1
             time.sleep(0.5) # Short delay
        else:
            print(f"Failed to add JD '{title}' to the database.")

    print(f"--- Finished processing {processed_count} Job Descriptions ({skipped_summary} summaries skipped) ---")


def process_cvs(conn: sqlite3.Connection, cv_directory: str):
    """Lists PDFs, extracts text, adds candidates to DB, and triggers extraction."""
    print("\n--- Processing Candidate CVs ---")
    try:
        pdf_files = list_pdf_files(cv_directory)
    except (NotADirectoryError, Exception) as e:
        print(f"Error listing PDF files in {cv_directory}: {e}. Skipping CV processing.")
        return

    processed_count = 0
    skipped_extraction = 0
    for pdf_path in pdf_files:
        # print(f"\nProcessing CV: {pdf_path.name}") # Reduces verbosity
        cv_text = extract_text_from_pdf(str(pdf_path))

        if not cv_text or len(cv_text) < 50:
            print(f"Skipping {pdf_path.name} due to empty or short extracted text.")
            continue

        # Add candidate to database (or get existing ID)
        candidate_id = add_candidate(conn, pdf_path.name, cv_text)

        if candidate_id != -1:
            # Check if extraction already exists (Optimization)
            cursor = conn.cursor()
            cursor.execute("SELECT extracted_data_json FROM candidates WHERE candidate_id = ?", (candidate_id,))
            existing_data = cursor.fetchone()
            if existing_data and existing_data['extracted_data_json']:
                 # print(f"Skipping extraction for Candidate ID {candidate_id}, data already exists.") # Reduces verbosity
                 skipped_extraction += 1
                 processed_count +=1
                 continue

            # Trigger CV extraction agent
            extracted_data = extract_cv_data(candidate_id, cv_text)
            if extracted_data:
                update_candidate_extraction(conn, candidate_id, extracted_data)
            processed_count += 1
            time.sleep(0.5) # Short delay
        else:
            print(f"Failed to add candidate for CV '{pdf_path.name}' to the database.")

    print(f"--- Finished processing {processed_count} CVs ({skipped_extraction} extractions skipped) ---")

# +++ NEW FUNCTION for Matching/Shortlisting Orchestration +++
def run_matching_and_shortlisting(conn: sqlite3.Connection):
    """Orchestrates the matching and shortlisting process for all JDs."""
    print("\n--- Starting Matching and Shortlisting Phase ---")
    all_jd_ids = get_all_jd_ids(conn)
    all_candidate_ids = get_all_candidate_ids(conn)

    if not all_jd_ids or not all_candidate_ids:
        print("No JDs or Candidates found in the database. Cannot run matching.")
        return

    total_matches_calculated = 0
    print(f"Calculating matches for {len(all_jd_ids)} JDs against {len(all_candidate_ids)} candidates...")

    # --- Calculate Scores for all JD-Candidate Pairs ---
    for jd_id in all_jd_ids:
        print(f"  Matching for JD ID: {jd_id}")
        # Check if JD has summary data before proceeding
        cursor = conn.cursor()
        cursor.execute("SELECT summary_json FROM job_descriptions WHERE jd_id = ?", (jd_id,))
        jd_summary_check = cursor.fetchone()
        if not jd_summary_check or not jd_summary_check['summary_json']:
             print(f"    Skipping JD {jd_id} - Missing summary data.")
             continue

        for candidate_id in all_candidate_ids:
            # Optional: Check if candidate has data before scoring
            cursor.execute("SELECT extracted_data_json FROM candidates WHERE candidate_id = ?", (candidate_id,))
            cand_data_check = cursor.fetchone()
            if not cand_data_check or not cand_data_check['extracted_data_json']:
                 # print(f"    Skipping Candidate {candidate_id} for JD {jd_id} - Missing extracted data.") # Verbose
                 continue

            # Calculate score
            score, details = calculate_match_score(jd_id, candidate_id, conn)

            # Save score to DB
            if score is not None:
                add_or_update_match(conn, jd_id, candidate_id, score, details)
                total_matches_calculated += 1
            # else: # Score is None (likely missing data) - already printed in calculate_match_score
                # print(f"    Score calculation failed for JD {jd_id} / Cand {candidate_id}.")

        # Optional delay per JD if needed
        # time.sleep(0.1)

    print(f"\n--- Calculated and stored {total_matches_calculated} match scores ---")

    # --- Run Shortlisting for each JD ---
    all_shortlisted_info = {}
    for jd_id in all_jd_ids:
        shortlisted_for_jd = shortlist_candidates_for_jd(jd_id, conn)
        if shortlisted_for_jd:
             all_shortlisted_info[jd_id] = shortlisted_for_jd
        # Optional delay per JD
        # time.sleep(0.1)

    print("\n--- Shortlisting Phase Complete ---")
    # Optional: Print summary of shortlists
    if all_shortlisted_info:
        print("\nSummary of Shortlisted Candidates per JD:")
        for jd_id, candidates in all_shortlisted_info.items():
            print(f"  JD ID {jd_id}: {len(candidates)} candidates shortlisted.")
            # for cand in candidates[:3]: # Print top 3 for brevity
            #     print(f"    - Cand ID {cand['candidate_id']} ({cand['cv_filename']}), Score: {cand['match_score']}")
    else:
        print("No candidates were shortlisted based on the current threshold and scores.")

# +++ END NEW FUNCTION +++


if __name__ == "__main__":
    start_time = time.time()
    print("Starting Job Screening Data Processing Pipeline...")

    try:
        config = load_config()
        db_path = config['database_path']
        cv_dir = config['cv_directory']
        jd_csv = config['jd_csv_path']

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = get_db_connection(db_path)
        create_tables(conn) # Ensure tables exist

        # --- Run Processing Steps ---
        # V V V ENSURE THESE ARE NOT COMMENTED OUT V V V
        process_job_descriptions(conn, jd_csv)
        process_cvs(conn, cv_dir)
        # ^ ^ ^ ENSURE THESE ARE NOT COMMENTED OUT ^ ^ ^

        # --- Run Matching/Shortlisting AFTER processing ---
        run_matching_and_shortlisting(conn)
        # ------------------------------------------------

        conn.close()
        print("\nDatabase connection closed.")

    # ... (rest of the error handling and timing code) ...

    except Exception as e:
        print(f"\nFATAL ERROR in main pipeline: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals() and conn:
            conn.close()
            print("Database connection closed due to error.")

    end_time = time.time()
    print(f"\nTotal execution time: {end_time - start_time:.2f} seconds.")
    print("Pipeline finished.")
