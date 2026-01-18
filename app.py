import streamlit as st
import pandas as pd
import json
import random
import contextlib
import sys
from datetime import date
from schedule_surgery import parsing, days, optimize

# --- 1. THE REDIRECT CLASS (Put this at the top) ---
class StStdout:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.output = ""

    def write(self, text):
        self.output += text
        self.placeholder.code(self.output)

    def flush(self):
        pass

# --- 2. THE UI SETUP ---
st.set_page_config(page_title="Surgery Scheduler", layout="wide")
st.title("🏥 Surgery Schedule Optimizer")

col1, col2 = st.columns(2)
with col1:
    zelje_file = st.file_uploader("Upload zelje.tsv", type=["tsv"])
    mastersheet_file = st.file_uploader("Upload mastersheet_file.tsv", type=["tsv"])
with col2:
    preschedule_file = st.file_uploader("Upload preschedule.tsv", type=["tsv"])
    config_file = st.file_uploader("Upload config.json", type=["json"])

# --- 3. THE TRIGGER BUTTON ---
if st.button("🚀 Generate Schedule"):
    if not all([zelje_file, mastersheet_file, preschedule_file, config_file]):
        st.error("Please upload all four files first!")
    else:
        # Create a UI spot for the terminal logs
        st.subheader("Processing Logs")
        log_container = st.empty()

        # --- 4. THE REDIRECTION BLOCK ---
        with contextlib.redirect_stdout(StStdout(log_container)):
            # Everything inside this block that uses 'print()'
            # will now show up in the 'log_container' above.

            config = json.load(config_file)
            start_date = date.fromisoformat(config["start_date"])
            end_date = date.fromisoformat(config["end_date"])

            day_list = days.generate_day_list(start_date=start_date, end_date=end_date)
            worker_list = parsing.parse_workers(zelje_file, mastersheet_file)
            preschedule = parsing.parse_preschedule(preschedule_file)

            # This print will appear in the web UI:
            print(f"Generating schedule for {len(day_list)} days...")

            random.shuffle(worker_list)

            # Your library call
            schedule_array, stats_array = optimize.construct_and_optimize(
                worker_list=worker_list,
                day_list=day_list,
                preschedule=preschedule,
                config=config
            )

        # --- 5. RESULTS DISPLAY (After redirection ends) ---
        st.success("Optimization Complete!")

        # Convert those list-of-lists into DataFrames
        df_schedule = pd.DataFrame(schedule_array)
        df_stats = pd.DataFrame(stats_array)

        st.subheader("Schedule Preview")
        st.dataframe(df_schedule)

        # Download buttons
        tsv_schedule = df_schedule.to_csv(sep='\t', index=False).encode('utf-8')
        st.download_button("📥 Download Schedule (.tsv)", tsv_schedule, "schedule.tsv")