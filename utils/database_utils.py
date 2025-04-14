# utils/database_utils.py
import sqlite3
from pathlib import Path
import json
import datetime

def get_db_connection(db_path: str):
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        print(f"Database connection established to {db_path}")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database {db_path}: {e}")
        raise

def create_tables(conn: sqlite3.Connection):
    """Creates the necessary tables if they don't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_descriptions (
                jd_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_description TEXT,
                summary_json TEXT, -- Store structured summary as JSON string
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cv_filename TEXT UNIQUE NOT NULL, -- Unique constraint for filename
                cv_text TEXT, -- Store full extracted text if needed
                extracted_data_json TEXT, -- Store structured extracted data as JSON
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                jd_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                match_score REAL, -- Use REAL for float scores
                shortlist_status BOOLEAN DEFAULT 0, -- 0=No, 1=Yes
                match_details_json TEXT, -- Optional: Store details about the match factors
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (jd_id) REFERENCES job_descriptions (jd_id),
                FOREIGN KEY (candidate_id) REFERENCES candidates (candidate_id),
                UNIQUE (jd_id, candidate_id) -- Ensure only one match entry per JD/candidate pair
            )
        ''')
        conn.commit()
        print("Tables checked/created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating tables: {e}")
        conn.rollback() # Rollback changes if error occurs
        raise

# --- Placeholder functions for CRUD operations (Implement as needed by agents) ---

def add_job_description(conn: sqlite3.Connection, title: str, description: str) -> int:
    """Adds a new job description and returns its ID."""
    sql = 'INSERT INTO job_descriptions (title, original_description) VALUES (?, ?)'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (title, description))
        conn.commit()
        print(f"Added job description: {title}")
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error adding job description {title}: {e}")
        conn.rollback()
        return -1 # Indicate error

def update_jd_summary(conn: sqlite3.Connection, jd_id: int, summary: dict):
    """Updates the summary for a given job description ID."""
    sql = 'UPDATE job_descriptions SET summary_json = ? WHERE jd_id = ?'
    try:
        cursor = conn.cursor()
        summary_str = json.dumps(summary) # Convert dict to JSON string
        cursor.execute(sql, (summary_str, jd_id))
        conn.commit()
        print(f"Updated summary for JD ID: {jd_id}")
        return True
    except sqlite3.Error as e:
        print(f"Error updating summary for JD ID {jd_id}: {e}")
        conn.rollback()
        return False

def add_candidate(conn: sqlite3.Connection, cv_filename: str, cv_text: str) -> int:
    """Adds a candidate or returns existing ID if filename exists. Returns ID."""
    # Check if candidate already exists
    cursor = conn.cursor()
    cursor.execute("SELECT candidate_id FROM candidates WHERE cv_filename = ?", (cv_filename,))
    result = cursor.fetchone()
    if result:
        print(f"Candidate {cv_filename} already exists with ID: {result['candidate_id']}")
        return result['candidate_id']

    # Add new candidate
    sql = 'INSERT INTO candidates (cv_filename, cv_text) VALUES (?, ?)'
    try:
        cursor.execute(sql, (cv_filename, cv_text))
        conn.commit()
        print(f"Added candidate: {cv_filename}")
        return cursor.lastrowid
    except sqlite3.IntegrityError: # Should be caught by the check above, but good practice
         print(f"Integrity error likely means {cv_filename} was added concurrently.")
         conn.rollback()
         # Re-fetch to be sure
         cursor.execute("SELECT candidate_id FROM candidates WHERE cv_filename = ?", (cv_filename,))
         result = cursor.fetchone()
         return result['candidate_id'] if result else -1
    except sqlite3.Error as e:
        print(f"Error adding candidate {cv_filename}: {e}")
        conn.rollback()
        return -1

def update_candidate_extraction(conn: sqlite3.Connection, candidate_id: int, extracted_data: dict):
    """Updates the extracted data for a given candidate ID."""
    sql = 'UPDATE candidates SET extracted_data_json = ? WHERE candidate_id = ?'
    try:
        cursor = conn.cursor()
        data_str = json.dumps(extracted_data)
        cursor.execute(sql, (data_str, candidate_id))
        conn.commit()
        print(f"Updated extracted data for Candidate ID: {candidate_id}")
        return True
    except sqlite3.Error as e:
        print(f"Error updating extraction for Candidate ID {candidate_id}: {e}")
        conn.rollback()
        return False

def add_or_update_match(conn: sqlite3.Connection, jd_id: int, candidate_id: int, score: float, details: dict = None):
    """Adds or updates a match score between a JD and a candidate."""
    sql = '''
        INSERT INTO matches (jd_id, candidate_id, match_score, match_details_json, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(jd_id, candidate_id) DO UPDATE SET
            match_score = excluded.match_score,
            match_details_json = excluded.match_details_json,
            timestamp = excluded.timestamp
    '''
    try:
        cursor = conn.cursor()
        details_str = json.dumps(details) if details else None
        now = datetime.datetime.now()
        cursor.execute(sql, (jd_id, candidate_id, score, details_str, now))
        conn.commit()
        print(f"Added/Updated match for JD {jd_id} and Candidate {candidate_id} with score {score:.2f}")
        return True
    except sqlite3.Error as e:
        print(f"Error adding/updating match for JD {jd_id}, Cand {candidate_id}: {e}")
        conn.rollback()
        return False

# Add functions for retrieving data (get_jd, get_candidate, get_matches, get_shortlisted etc.) as needed
# utils/database_utils.py
# ... (keep existing functions like get_db_connection, create_tables, add_*, update_*) ...

# +++ NEW FUNCTIONS START HERE +++

def get_jd(conn: sqlite3.Connection, jd_id: int) -> sqlite3.Row | None:
    """Retrieves a job description row by its ID."""
    sql = 'SELECT * FROM job_descriptions WHERE jd_id = ?'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (jd_id,))
        row = cursor.fetchone()
        if row:
            # print(f"Retrieved JD data for ID: {jd_id}")
            return row
        else:
            print(f"No JD found with ID: {jd_id}")
            return None
    except sqlite3.Error as e:
        print(f"Error retrieving JD ID {jd_id}: {e}")
        return None

def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> sqlite3.Row | None:
    """Retrieves a candidate row by its ID."""
    sql = 'SELECT * FROM candidates WHERE candidate_id = ?'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (candidate_id,))
        row = cursor.fetchone()
        if row:
            # print(f"Retrieved Candidate data for ID: {candidate_id}")
            return row
        else:
            print(f"No Candidate found with ID: {candidate_id}")
            return None
    except sqlite3.Error as e:
        print(f"Error retrieving Candidate ID {candidate_id}: {e}")
        return None

def get_all_jd_ids(conn: sqlite3.Connection) -> list[int]:
    """Retrieves all job description IDs from the database."""
    sql = 'SELECT jd_id FROM job_descriptions'
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        # Fetch all rows and extract the first element (jd_id) from each tuple
        ids = [row[0] for row in cursor.fetchall()]
        print(f"Retrieved {len(ids)} JD IDs.")
        return ids
    except sqlite3.Error as e:
        print(f"Error retrieving all JD IDs: {e}")
        return []

def get_all_candidate_ids(conn: sqlite3.Connection) -> list[int]:
    """Retrieves all candidate IDs from the database."""
    sql = 'SELECT candidate_id FROM candidates'
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        ids = [row[0] for row in cursor.fetchall()]
        print(f"Retrieved {len(ids)} Candidate IDs.")
        return ids
    except sqlite3.Error as e:
        print(f"Error retrieving all Candidate IDs: {e}")
        return []

def get_matches_for_jd(conn: sqlite3.Connection, jd_id: int) -> list[sqlite3.Row]:
     """Retrieves all match rows for a given job description ID."""
     sql = '''
        SELECT m.*, c.cv_filename
        FROM matches m
        JOIN candidates c ON m.candidate_id = c.candidate_id
        WHERE m.jd_id = ?
        ORDER BY m.match_score DESC
     '''
     try:
         cursor = conn.cursor()
         cursor.execute(sql, (jd_id,))
         rows = cursor.fetchall()
         # print(f"Retrieved {len(rows)} matches for JD ID: {jd_id}")
         return rows
     except sqlite3.Error as e:
         print(f"Error retrieving matches for JD ID {jd_id}: {e}")
         return []

def update_shortlist_status(conn: sqlite3.Connection, match_id: int, status: bool):
    """Updates the shortlist status for a given match ID."""
    sql = 'UPDATE matches SET shortlist_status = ? WHERE match_id = ?'
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (int(status), match_id)) # Store boolean as 0 or 1
        conn.commit()
        # print(f"Updated shortlist status to {status} for Match ID: {match_id}")
        return True
    except sqlite3.Error as e:
        print(f"Error updating shortlist status for Match ID {match_id}: {e}")
        conn.rollback()
        return False

# +++ NEW FUNCTIONS END HERE +++

# ... (keep the rest of the file, including if __name__ == '__main__': block) ...
# --- Example Usage (optional, for testing) ---
if __name__ == '__main__':
    from config_loader import load_config
    try:
        config = load_config()
        db_path = config['database_path']

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = get_db_connection(db_path)
        create_tables(conn)

        print("\n--- Testing DB Operations ---")
        # Example: Add a dummy JD
        dummy_jd_id = add_job_description(conn, "Dummy Role", "This is a test description.")
        if dummy_jd_id != -1:
             print(f"Dummy JD added with ID: {dummy_jd_id}")
             # Example: Update its summary
             update_jd_summary(conn, dummy_jd_id, {"skills": ["test"], "experience": "1 year"})

        # Example: Add a dummy candidate
        dummy_cand_id = add_candidate(conn, "dummy_cv.pdf", "Candidate text here.")
        if dummy_cand_id != -1:
             print(f"Dummy Candidate added with ID: {dummy_cand_id}")
             # Example: Update extracted data
             update_candidate_extraction(conn, dummy_cand_id, {"name": "Dummy", "skills": ["python"]})

        # Example: Add a match
        if dummy_jd_id != -1 and dummy_cand_id != -1:
            add_or_update_match(conn, dummy_jd_id, dummy_cand_id, 0.85, {"skill_match": 0.9})

        print("\nDatabase operations test complete.")
        conn.close()
        print("Database connection closed.")

    except Exception as e:
        print(f"\nAn error occurred during DB testing: {e}")
        if 'conn' in locals() and conn:
            conn.close()