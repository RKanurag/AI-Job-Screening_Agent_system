# ui/app.py
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import time
import sqlite3
import json
import logging # Import logging

# --- Set Page Config FIRST ---
# Should be the very first Streamlit command
st.set_page_config(layout="wide")

# --- Add project root to sys.path ---
# This allows Streamlit to find your utility and agent modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
# --- End sys.path modification ---

# Import necessary functions AFTER potentially modifying sys.path
try:
    from utils.config_loader import load_config
    from utils.database_utils import (
        get_db_connection, create_tables, get_all_jd_ids, get_jd,
        get_matches_for_jd, get_candidate # Make sure all needed funcs are imported
    )
    # Needed to display JD list - consider getting titles directly from DB instead
    # from utils.file_parsers import read_job_descriptions_from_csv
    from agents.scheduler_agent import generate_interview_requests
except ImportError as e:
    st.error(f"Import Error: {e}. Please ensure all required modules are accessible.")
    st.stop()


# --- Load Config and Connect to DB ---
try:
    config = load_config()
    db_path = config['database_path']
    # Ensure DB exists - main.py should have created it
    if not Path(db_path).is_file():
         st.error(f"Database file not found at {db_path}. Please run the main processing pipeline first (`python main.py`).")
         st.stop() # Stop execution if DB doesn't exist

    # Temporary modification - caching disabled for debugging
    def get_cached_db_connection(path):
        try:
            conn = sqlite3.connect(path, uri=False, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            logging.info(f"New DB connection established to {path}")
            return conn
        except sqlite3.Error as e:
             st.error(f"Error connecting to database {path}: {e}")
             return None

    conn = get_cached_db_connection(db_path)
    if conn is None:
        st.stop()

    # Temporary modification - caching disabled for debugging
    def load_jd_titles(_conn):
        logging.info("Loading fresh JD titles data")
        try:
            cursor = _conn.cursor()
            cursor.execute("SELECT jd_id, title FROM job_descriptions ORDER BY title")
            jds = cursor.fetchall()
            jd_dict = {row['jd_id']: row['title'] for row in jds}
            jd_options = [(row['jd_id'], f"{row['title']} (ID: {row['jd_id']})") for row in jds]
            return jd_dict, jd_options
        except Exception as e:
            st.error(f"Error loading Job Description titles: {e}")
            return {}, []

    jd_titles_map, jd_select_options = load_jd_titles(conn)

except Exception as e:
    st.error(f"Failed during startup (config/db/jd_titles): {e}")
    st.stop()


# --- Helper Function for Display ---
def format_json_display(json_data):
    """
    Helper function to prepare dict for display, handling None/empty lists.
    Returns a new dictionary with values formatted for display.
    """
    if not isinstance(json_data, dict):
        return {} # Return empty dict if input is not a dict

    display_data = {}
    for key, value in json_data.items():
        if value is None:
            display_data[key] = "Not Specified"
        elif isinstance(value, list) and not value:
             # For lists that are empty, return a special placeholder LIST for consistent handling later
            display_data[key] = ["--- None Provided ---"] # Use a list containing a placeholder string
        elif isinstance(value, list):
            # Ensure all list items are strings for display
            display_data[key] = [str(item) for item in value if item is not None] # Filter out None in list too
            # If filtering made the list empty, use placeholder
            if not display_data[key]:
                display_data[key] = ["--- None Provided ---"]
        else:
            display_data[key] = value # Keep other types as they are (numbers, strings etc)
    return display_data


# --- Streamlit App Layout ---
st.title("🤖 AI-Powered Job Screening Assistant")
st.markdown("View candidate match scores and shortlist status for selected job descriptions.")

# --- Sidebar for Selection ---
with st.sidebar: # Group sidebar elements
    st.header("Select Job Description")

    # Create display text list for selectbox
    # Ensure jd_select_options is not empty before proceeding
    if not jd_select_options:
        st.warning("No Job Descriptions found in the database.")
        selectbox_options = ["--- No JDs Available ---"]
    else:
        selectbox_options = [option[1] for option in jd_select_options]
        # Add a placeholder option
        selectbox_options.insert(0, "--- Select a Job Description ---")

    selected_jd_display_text = st.selectbox(
        "Choose a Job:",
        options=selectbox_options,
        index=0 # Default to placeholder
    )

    st.markdown("---")
    if st.button("Clear Cache & Refresh Data"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.info("Ensure `python main.py` has been run to populate the database.")

# Find the selected JD ID based on the display text
selected_jd_id = None
if selected_jd_display_text not in ["--- Select a Job Description ---", "--- No JDs Available ---"]:
    # Find the ID corresponding to the selected display text
    for jd_id, display_text in jd_select_options:
        if display_text == selected_jd_display_text:
            selected_jd_id = jd_id
            break


# --- Main Area for Display ---
if selected_jd_id:
    st.header(f"Results for: {jd_titles_map.get(selected_jd_id, 'Unknown Title')}")

    # Display JD Summary
    with st.expander("View Job Description Summary", expanded=False):
        # Retrieve JD data within the expander context
        jd_row = get_jd(conn, selected_jd_id)
        if jd_row and jd_row['summary_json']:
            try:
                summary_data = json.loads(jd_row['summary_json'])
                formatted_summary = format_json_display(summary_data)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### Required Skills")
                    req_skills = formatted_summary.get('required_skills', ["--- None Provided ---"])
                    if req_skills != ["--- None Provided ---"]:
                        for skill in req_skills: st.markdown(f"- {skill}")
                    else: st.write("None Provided")

                    st.markdown("##### Required Experience")
                    st.write(formatted_summary.get('required_experience_years', 'Not Specified'))

                    st.markdown("##### Required Education")
                    st.write(formatted_summary.get('required_education', 'Not Specified'))

                with col2:
                    st.markdown("##### Key Responsibilities")
                    resp = formatted_summary.get('key_responsibilities', ["--- None Provided ---"])
                    if resp != ["--- None Provided ---"]:
                        for r in resp: st.markdown(f"- {r}")
                    else: st.write("None Provided")

                    # Check preferred skills - use the placeholder check
                    pref_skills = formatted_summary.get('preferred_skills', ["--- None Provided ---"])
                    if pref_skills != ["--- None Provided ---"]:
                        st.markdown("##### Preferred Skills")
                        for skill in pref_skills: st.markdown(f"- {skill}")

                    # Check soft skills - use the placeholder check
                    soft_skills = formatted_summary.get('soft_skills', ["--- None Provided ---"])
                    if soft_skills != ["--- None Provided ---"]:
                        st.markdown("##### Soft Skills")
                        for skill in soft_skills: st.markdown(f"- {skill}")

            except json.JSONDecodeError:
                st.warning("Could not parse JD summary JSON.")
            except Exception as e:
                st.error(f"Error displaying JD summary: {e}")
        elif jd_row:
             st.warning("Summary JSON not available for this JD.")
        else:
             st.error("Could not retrieve JD details.")

    # Display Matches and Shortlist
    st.subheader("Candidate Matches")
    try:
        # Retrieve matches within a try-except block
        matches = get_matches_for_jd(conn, selected_jd_id) # Assumes sorted by score DESC
    except Exception as e:
        st.error(f"Error retrieving matches from database: {e}")
        matches = [] # Set matches to empty list on error

    if not matches:
        st.warning("No candidates have been matched for this job description yet.")
        # st.info("Ensure the main processing pipeline (`python main.py`) has been run successfully.") # Redundant with sidebar info
    else:
        match_data_for_df = []
        shortlisted_candidates_for_email = [] # Collect data for email generation
        for match in matches:
            is_shortlisted = bool(match['shortlist_status'])
            # score_display = f"{match['match_score']:.3f}" # Format later in dataframe config
            status_display = "✅ Shortlisted" if is_shortlisted else "⏳ Under Review"

            match_data_for_df.append({
                "Candidate ID": match['candidate_id'],
                "CV Filename": match['cv_filename'],
                "Match Score": float(match['match_score']),  # Keep as float for sorting
                "Status": status_display
            })
            if is_shortlisted:
                 shortlisted_candidates_for_email.append({
                      "candidate_id": match['candidate_id'],
                      "cv_filename": match['cv_filename']
                 })

        # Create and display DataFrame
        if match_data_for_df:
            match_df = pd.DataFrame(match_data_for_df)
            # Sort by Match Score descending before display
            match_df = match_df.sort_values(by="Match Score", ascending=False)

            st.dataframe(
                match_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Candidate ID": st.column_config.NumberColumn("ID", width="small"),
                    "CV Filename": st.column_config.TextColumn("CV File"),
                    "Match Score": st.column_config.NumberColumn(
                        "Score",
                        help="Candidate match score (0-1)",
                        format="%.3f", # Format to 3 decimal places
                        width="small"
                    ),
                    "Status": st.column_config.TextColumn("Status", width="medium")
                }
            )
        else:
             st.info("No match data available to display.")


        # --- Top Candidates Details Section ---
        st.subheader("Top Candidates Details")

        # Limit to top 5 or fewer if less than 5 matches exist
        top_matches = matches[:min(5, len(matches))]

        if not top_matches:
             st.info("No candidates to display details for.")
        else:
            st.info("Details for the top matching candidates:")
            tab_titles = [f"#{i+1}: {match['cv_filename']} ({match['match_score']:.3f})"
                          for i, match in enumerate(top_matches)]

            tabs = st.tabs(tab_titles)

            for i, tab in enumerate(tabs):
                with tab:
                    match = top_matches[i] # Get the corresponding match data
                    cand_id = match['candidate_id']
                    cand_row = get_candidate(conn, cand_id) # Retrieve candidate data

                    if cand_row and cand_row['extracted_data_json']:
                        try:
                            cand_data = json.loads(cand_row['extracted_data_json'])
                            # Use the helper to format display values
                            formatted_data = format_json_display(cand_data)

                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("##### Technical Skills")
                                tech_skills = formatted_data.get('skills', ["--- None Provided ---"])
                                if tech_skills != ["--- None Provided ---"]:
                                    for skill in tech_skills: st.markdown(f"- {skill}")
                                else: st.write("None Provided")

                                st.markdown("##### Domain Expertise")
                                domain_skills = formatted_data.get('domain_expertise', ["--- None Provided ---"])
                                if domain_skills != ["--- None Provided ---"]:
                                    for domain in domain_skills: st.markdown(f"- {domain}")
                                else: st.write("None Provided")

                            with col2:
                                st.markdown("##### Experience")
                                st.write(f"Total Years: {formatted_data.get('total_experience_years', 'Not Specified')}")

                                st.markdown("##### Recent Roles")
                                titles_list = formatted_data.get('recent_job_titles', ["--- None Provided ---"])
                                if titles_list != ["--- None Provided ---"]:
                                    for title in titles_list: st.markdown(f"- {title}")
                                else: st.write("None Provided")

                                st.markdown("##### Certifications")
                                certs_list = formatted_data.get('certifications', ["--- None Provided ---"])
                                if certs_list != ["--- None Provided ---"]:
                                     for cert in certs_list: st.markdown(f"- {cert}")
                                else: st.write("None Provided") # Display correctly if empty/placeholder

                        except json.JSONDecodeError:
                            st.warning(f"Could not parse candidate JSON data for ID {cand_id}.")
                        except Exception as e:
                            st.error(f"Error displaying candidate details for ID {cand_id}: {e}")
                    else:
                        st.warning(f"No extracted data available for Candidate ID {cand_id}.")
                    # Display Match Details JSON if available
                    if match['match_details_json']:
                         with st.popover("View Match Score Details"): # Use popover for less clutter
                              try:
                                   details = json.loads(match['match_details_json'])
                                   st.json(details)
                              except json.JSONDecodeError:
                                   st.write("Could not parse score details.")


        # --- Generate Interview Emails ---
        st.subheader("Generate Interview Emails for Shortlisted Candidates")
        if not shortlisted_candidates_for_email:
            st.info("No candidates are currently shortlisted for this job.")
        else:
            st.markdown(f"Found **{len(shortlisted_candidates_for_email)}** shortlisted candidates.")
            if st.button("Generate Interview Request Emails"):
                # Add a visual indicator that something is happening
                email_placeholder = st.empty()
                email_placeholder.info("Generating email content...")
                try:
                    with st.spinner("Generating email content..."):
                        generated_emails = generate_interview_requests(selected_jd_id, shortlisted_candidates_for_email, conn)

                    email_placeholder.empty() # Remove the "Generating..." message

                    # DEBUG: Show generated_emails in Streamlit for troubleshooting
                    # st.write("DEBUG: generated_emails =", generated_emails)

                    if generated_emails:
                        for email_info in generated_emails:
                            with st.expander(f"Email for Candidate {email_info['candidate_id']} ({email_info['cv_filename']})"):
                                st.text_input(
                                    "Subject:",
                                    value=email_info['email_subject'],
                                    key=f"subject_{email_info['candidate_id']}_{selected_jd_id}"
                                )
                                st.text_area(
                                    "Body:",
                                    value=email_info['email_body'],
                                    height=250,
                                    key=f"body_{email_info['candidate_id']}_{selected_jd_id}"
                                )
                    else:
                        st.error("Failed to generate email content. Check agent logs.")
                except Exception as e:
                    email_placeholder.empty()
                    st.error(f"An error occurred during email generation: {e}")


else: # If no JD is selected
    st.info("👈 Select a job description from the sidebar to view matching candidates.")
