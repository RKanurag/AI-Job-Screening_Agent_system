# utils/file_parsers.py
import pandas as pd
from pathlib import Path
from io import StringIO
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
import sqlite3

def read_job_descriptions_from_csv(csv_path: str) -> pd.DataFrame:
    """Reads job descriptions from a CSV file into a pandas DataFrame."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Job description CSV file not found at {csv_path}")
    try:
        # Assuming standard CSV format, adjust parameters if needed (e.g., delimiter)
        df = pd.read_csv(path, encoding="ISO-8859-1")  # Change encoding here
        # Basic validation: Check for expected columns (adjust names if different)
        if 'Job Title' not in df.columns or 'Job Description' not in df.columns:
             raise ValueError("CSV must contain 'Job Title' and 'Job Description' columns")
        print(f"Successfully read {len(df)} job descriptions from {csv_path}")
        return df
    except Exception as e:
        print(f"Error reading CSV {csv_path}: {e}")
        raise

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text content from a PDF file using pdfminer.six."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    try:
        # Adjust LAParams for potentially better layout analysis if needed
        laparams = LAParams()
        text = extract_text(path, laparams=laparams)
        print(f"Successfully extracted text from {pdf_path}")
        return text
    except Exception as e:
        # Log the error and return an empty string for invalid PDFs
        print(f"Error extracting text from PDF {pdf_path}: {e}")
        return ""

def list_pdf_files(directory: str) -> list[Path]:
    """Lists all PDF files in the specified directory."""
    path = Path(directory)
    if not path.is_dir():
        raise NotADirectoryError(f"CV directory not found at {directory}")
    pdf_files = list(path.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {directory}")
    return pdf_files

def extract_and_store_cv_texts(cv_directory: str, db_path: str):
    """
    Extracts text from all PDF files in the specified directory and stores them in the database.

    Args:
        cv_directory: Path to the directory containing CV PDFs.
        db_path: Path to the SQLite database.
    """
    from pathlib import Path

    # List all PDF files in the directory
    pdf_files = list_pdf_files(cv_directory)

    # Connect to the database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for pdf_file in pdf_files:
        try:
            # Extract text from the PDF
            cv_text = extract_text_from_pdf(str(pdf_file))

            if not cv_text.strip():
                print(f"Skipping {pdf_file.name}: No text extracted or file is corrupted.")
                continue

            # Insert or update the candidate in the database
            cursor.execute(
                """
                INSERT INTO candidates (cv_filename, cv_text)
                VALUES (?, ?)
                ON CONFLICT(cv_filename) DO UPDATE SET cv_text=excluded.cv_text
                """,
                (pdf_file.name, cv_text)
            )
            print(f"Processed and stored text for {pdf_file.name}")

        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")

    # Commit changes and close the connection
    conn.commit()
    conn.close()

# --- Example Usage (optional, for testing) ---
if __name__ == '__main__':
    from config_loader import load_config
    try:
        config = load_config()
        print("\n--- Testing CSV Reader ---")
        jds_df = read_job_descriptions_from_csv(config['jd_csv_path'])
        print("Job Descriptions DataFrame Head:")
        print(jds_df.head())

        print("\n--- Testing PDF Lister ---")
        cv_files = list_pdf_files(config['cv_directory'])
        if cv_files:
            print(f"First 5 CV files found: {[f.name for f in cv_files[:5]]}")

            print("\n--- Testing PDF Extractor (on first CV) ---")
            if cv_files:
                first_cv_path = cv_files[0]
                cv_text = extract_text_from_pdf(str(first_cv_path))
                print(f"\nExtracted Text from {first_cv_path.name} (first 500 chars):")
                print(cv_text[:500] + "...")
            else:
                print("No CV files found in the directory to test extraction.")

        print("\n--- Extracting and Storing CV Texts ---")
        extract_and_store_cv_texts(config['cv_directory'], config['database_path'])

    except Exception as e:
        print(f"\nAn error occurred during testing: {e}")