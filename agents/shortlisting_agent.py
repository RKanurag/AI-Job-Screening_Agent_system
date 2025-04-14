# agents/shortlisting_agent.py
import sys
from pathlib import Path
import json
import sqlite3

# --- Add project root to sys.path ---
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

from utils.database_utils import get_matches_for_jd, update_shortlist_status, get_db_connection
from utils.config_loader import load_config

# Load config for threshold
try:
    config = load_config()
    SHORTLISTING_THRESHOLD = config.get('shortlisting_threshold', 0.75)
    print(f"Shortlisting Agent using threshold: {SHORTLISTING_THRESHOLD}")
except Exception as e:
    print(f"Error loading config for shortlisting threshold: {e}. Using default 0.75.")
    SHORTLISTING_THRESHOLD = 0.75

def shortlist_candidates_for_jd(jd_id: int, conn: sqlite3.Connection) -> list[dict]:
    """
    Identifies and updates shortlist status for candidates matching a JD above the threshold.

    Args:
        jd_id: The job description database ID.
        conn: Active database connection.

    Returns:
        A list of dictionaries, each representing a shortlisted candidate
        (including candidate_id, cv_filename, match_score).
    """
    print(f"\n--- Shortlisting candidates for JD ID: {jd_id} (Threshold: {SHORTLISTING_THRESHOLD:.2f}) ---")
    shortlisted_candidates = []
    all_matches = get_matches_for_jd(conn, jd_id) # Assumes matches are sorted DESC by score

    if not all_matches:
        print(f"No match scores found for JD ID: {jd_id}. Cannot shortlist.")
        return []

    updated_count = 0
    for match_row in all_matches:
        match_id = match_row['match_id']
        candidate_id = match_row['candidate_id']
        score = match_row['match_score']
        cv_filename = match_row['cv_filename'] # Added cv_filename in get_matches_for_jd

        if score >= SHORTLISTING_THRESHOLD:
            status = True
            shortlisted_candidates.append({
                "candidate_id": candidate_id,
                "cv_filename": cv_filename,
                "match_score": round(score, 3)
            })
            print(f"  [+] Shortlisted: Candidate {candidate_id} ({cv_filename}), Score: {score:.3f}")
        else:
            status = False
            # Optional: print those below threshold
            # print(f"  [-] Below Threshold: Candidate {candidate_id} ({cv_filename}), Score: {score:.3f}")

        # Update status in DB regardless (to reset previous shortlistings if score changed)
        success = update_shortlist_status(conn, match_id, status)
        if success:
            updated_count +=1
        else:
             print(f"  Warning: Failed to update shortlist status for Match ID {match_id}")

    print(f"--- Finished shortlisting for JD ID: {jd_id}. Found {len(shortlisted_candidates)} candidates meeting threshold. Updated {updated_count} statuses. ---")
    return shortlisted_candidates


# --- Example Usage (for testing this agent) ---
if __name__ == '__main__':
    print("--- Testing Shortlisting Agent ---")
    try:
        config = load_config()
        db_path = config['database_path']
        conn = get_db_connection(db_path)

        # --- Get a JD that likely has matches (e.g., the one tested in matching_agent) ---
        cursor = conn.cursor()
        # Find a JD ID that exists in the matches table
        cursor.execute("SELECT DISTINCT jd_id FROM matches LIMIT 1")
        match_res = cursor.fetchone()

        if match_res:
            test_jd_id = match_res['jd_id']
            print(f"\nTesting shortlisting for JD ID: {test_jd_id}")

            shortlisted = shortlist_candidates_for_jd(test_jd_id, conn)

            if shortlisted:
                print("\nShortlisted Candidates:")
                for candidate in shortlisted:
                    print(f" - ID: {candidate['candidate_id']}, File: {candidate['cv_filename']}, Score: {candidate['match_score']}")
            else:
                print("\nNo candidates met the shortlisting threshold for this JD.")

        else:
            print("\nCould not find any processed matches in the database to test shortlisting.")
            print("Hint: Run main.py or matching_agent.py test first.")

        conn.close()

    except Exception as e:
        print(f"\nAn error occurred during Shortlisting Agent test: {e}")
        if 'conn' in locals() and conn:
             conn.close()