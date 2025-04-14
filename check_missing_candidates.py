import sqlite3
from utils.config_loader import load_config

def main():
    config = load_config()
    db_path = config['database_path']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    # Get all shortlisted candidate IDs from matches
    cursor.execute("SELECT DISTINCT candidate_id FROM matches WHERE shortlist_status = 1")
    shortlisted_ids = [row['candidate_id'] for row in cursor.fetchall()]

    # Get all candidate IDs from candidates table
    cursor.execute("SELECT candidate_id FROM candidates")
    candidate_ids = set(row['candidate_id'] for row in cursor.fetchall())

    # Find missing candidate IDs
    missing = [cid for cid in shortlisted_ids if cid not in candidate_ids]

    if missing:
        print(f'Missing candidate records for the following candidate IDs (shortlisted but not in candidates table): {missing}')
    else:
        print('All shortlisted candidate IDs exist in the candidates table.')

    conn.close()

if __name__ == '__main__':
    main()
