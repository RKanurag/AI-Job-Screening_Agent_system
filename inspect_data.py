import sqlite3
import json

def inspect_data(db_path):
    """Inspects the contents of the screening database with detailed error handling."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]
        print(f"\nFound tables: {tables}")

        print("\n=== Job Description Data ===")
        if 'job_descriptions' in tables:
            cursor.execute("SELECT COUNT(*) as count FROM job_descriptions")
            total_jds = cursor.fetchone()['count']
            print(f"Total JDs in database: {total_jds}")

            cursor.execute("SELECT COUNT(*) as count FROM job_descriptions WHERE summary_json IS NOT NULL")
            processed_jds = cursor.fetchone()['count']
            print(f"JDs with processed summaries: {processed_jds}")

            if processed_jds > 0:
                cursor.execute("SELECT jd_id, title, summary_json FROM job_descriptions WHERE summary_json IS NOT NULL LIMIT 1")
                jd = cursor.fetchone()
                if jd:
                    print(f"\nSample JD (ID: {jd['jd_id']}, Title: {jd['title']}):")
                    try:
                        summary = json.loads(jd['summary_json'])
                        print("Summary Data:")
                        print(json.dumps(summary, indent=2))
                    except json.JSONDecodeError as e:
                        print(f"Error decoding summary JSON: {e}")
                        print("Raw data:", jd['summary_json'][:200])

        print("\n=== Candidate Data ===")
        if 'candidates' in tables:
            cursor.execute("SELECT COUNT(*) as count FROM candidates")
            total_candidates = cursor.fetchone()['count']
            print(f"Total candidates in database: {total_candidates}")

            cursor.execute("SELECT COUNT(*) as count FROM candidates WHERE extracted_data_json IS NOT NULL")
            processed_candidates = cursor.fetchone()['count']
            print(f"Candidates with processed data: {processed_candidates}")

            if processed_candidates > 0:
                cursor.execute("SELECT candidate_id, cv_filename, extracted_data_json FROM candidates WHERE extracted_data_json IS NOT NULL LIMIT 1")
                cand = cursor.fetchone()
                if cand:
                    print(f"\nSample Candidate (ID: {cand['candidate_id']}, File: {cand['cv_filename']}):")
                    try:
                        data = json.loads(cand['extracted_data_json'])
                        print("Extracted Data:")
                        print(json.dumps(data, indent=2))
                    except json.JSONDecodeError as e:
                        print(f"Error decoding extracted data JSON: {e}")
                        print("Raw data:", cand['extracted_data_json'][:200])

        print("\n=== Match Data ===")
        if 'matches' in tables:
            cursor.execute("SELECT COUNT(*) as count FROM matches")
            total_matches = cursor.fetchone()['count']
            print(f"Total matches in database: {total_matches}")

            cursor.execute("SELECT COUNT(*) as count FROM matches WHERE match_score >= 0.75")  # Assuming 0.75 threshold
            shortlisted = cursor.fetchone()['count']
            print(f"Matches above 0.75 threshold: {shortlisted}")

            if total_matches > 0:
                cursor.execute("""
                    SELECT m.*, j.title as job_title, c.cv_filename 
                    FROM matches m 
                    JOIN job_descriptions j ON m.jd_id = j.jd_id 
                    JOIN candidates c ON m.candidate_id = c.candidate_id 
                    ORDER BY m.match_score DESC 
                    LIMIT 3
                """)
                print("\nTop 3 Matches:")
                for match in cursor.fetchall():
                    print(f"\nJob: {match['job_title']}")
                    print(f"Candidate: {match['cv_filename']}")
                    print(f"Score: {match['match_score']}")
                    try:
                        if match['match_details_json']:
                            details = json.loads(match['match_details_json'])
                            print("Match Details:")
                            print(json.dumps(details, indent=2))
                    except json.JSONDecodeError as e:
                        print(f"Error decoding match details: {e}")

        conn.close()

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An error occurred while inspecting the database: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    db_path = "data/screening_database.sqlite"
    inspect_data(db_path)