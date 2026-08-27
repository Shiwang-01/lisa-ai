import os
import pandas as pd
import streamlit as st
from lisa.protocol_floor import evaluate_protocol_floor

st.set_page_config(
    page_title="LISA.ai — ED Sequencing Prototype",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------
# Header & Disclaimer
# ---------------------------------------------------------
st.title("🏥 LISA.ai")
st.subheader("Dynamic ED Sequencing + Deterioration Safety Net")

st.warning(
    "⚠️ **Prototype simulation only — not for clinical use.**",
    icon="⚠️"
)

st.markdown("---")

# ---------------------------------------------------------
# Data Loading & Guardrail Evaluation
# ---------------------------------------------------------
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "seed_patients.csv")

@st.cache_data
def load_patient_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return df

try:
    patients_df = load_patient_data(DATA_PATH)
except Exception as e:
    st.error(f"Error loading dataset from {DATA_PATH}: {e}")
    st.stop()

# Evaluate Protocol Floors for entire cohort
floor_results = []
display_floor_labels = []

for _, row in patients_df.iterrows():
    res = evaluate_protocol_floor(row)
    floor_results.append(res)
    if res["triggered"]:
        display_floor_labels.append(f"Level {res['floor_level']}")
    else:
        display_floor_labels.append("No Hard Floor")

patients_display_df = patients_df.copy()
patients_display_df.insert(1, "protocol_floor", display_floor_labels)

# ---------------------------------------------------------
# Summary Metrics
# ---------------------------------------------------------
total_patients = len(patients_df)
pediatric_count = int((patients_df["age"] < 18).sum())
geriatric_count = int((patients_df["age"] >= 65).sum())
unavailable_records = int((patients_df["prior_record_available"].astype(str).str.strip().str.lower().isin(["no", "false", "0"])).sum())

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="👥 Patients Waiting", value=total_patients)

with col2:
    st.metric(label="👶 Pediatric Patients", value=pediatric_count)

with col3:
    st.metric(label="🧓 Geriatric Patients", value=geriatric_count)

with col4:
    st.metric(label="📁 Prior Records Unavailable", value=unavailable_records)

st.markdown("---")

# ---------------------------------------------------------
# Patient Cohort Data Table
# ---------------------------------------------------------
st.markdown("### 📋 Waiting ED Cohort")
st.dataframe(
    patients_display_df,
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# ---------------------------------------------------------
# Patient Inspection View
# ---------------------------------------------------------
st.markdown("### 🔍 Patient Inspection")

patient_tokens = patients_df["patient_token"].tolist()
options = [f"{token} — {patients_df.loc[patients_df['patient_token'] == token, 'complaint_text'].values[0]}" for token in patient_tokens]

selected_option = st.selectbox(
    "Select patient",
    options=options,
    index=0
)

selected_token = selected_option.split(" — ")[0]
selected_idx = patient_tokens.index(selected_token)
patient = patients_df.iloc[selected_idx]
patient_floor = floor_results[selected_idx]

# Display patient details in structured cards/columns
st.markdown(f"#### Patient Record: **{patient['patient_token']}**")

info_col1, info_col2, info_col3 = st.columns([1, 1, 1])

with info_col1:
    st.markdown("**Demographics & Status**")
    st.write(f"- **Age / Sex:** {patient['age']} yrs / {patient['sex']}")
    st.write(f"- **Language:** {patient['language']}")
    st.write(f"- **Pregnancy Status:** {patient['pregnancy_status']}")
    st.write(f"- **Arrived:** {patient['arrival_minutes_ago']} mins ago")

with info_col2:
    st.markdown("**Triage & Clinical Presentation**")
    st.write(f"- **Initial Triage Level:** ESI {patient['initial_triage_level']}")
    st.write(f"- **Mental Status:** {patient['mental_status']}")
    st.write(f"- **Visible Distress:** {patient['visible_distress']}")
    st.write(f"- **Pain Score:** {patient['pain_score']} / 10")

with info_col3:
    st.markdown("**Records & Resources**")
    st.write(f"- **Prior Records Available:** {patient['prior_record_available']}")
    st.write(f"- **Estimated Resource Need:** {patient['resource_need']}")
    st.write(f"- **Case Notes:** {patient['case_notes']}")

st.markdown("##### 🩺 Chief Complaint")
st.info(f"**{patient['complaint_text']}**")

st.markdown("##### 📊 Vital Signs")
vital_cols = st.columns(5)
vital_cols[0].metric(label="Heart Rate", value=f"{patient['heart_rate']} bpm")
vital_cols[1].metric(label="Respiratory Rate", value=f"{patient['respiratory_rate']} /min")
vital_cols[2].metric(label="Blood Pressure", value=f"{patient['systolic_bp']}/{patient['diastolic_bp']} mmHg")
vital_cols[3].metric(label="SpO2", value=f"{patient['spo2']}%")
vital_cols[4].metric(label="Temperature", value=f"{patient['temperature']} °C")

st.markdown("##### 📜 Known Medical History")
st.write(patient["known_history"])

# ---------------------------------------------------------
# Clinical Guardrails Section (Milestone 2)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 🛡️ Clinical Guardrails")

urgency_names = {
    1: "Immediate / Critical",
    2: "Emergent",
    3: "Urgent",
    4: "Less Urgent",
    5: "Non-Urgent"
}

if patient_floor["triggered"]:
    floor_lvl = patient_floor["floor_level"]
    urgency_label = urgency_names.get(floor_lvl, "Emergent")
    st.error(f"**Protocol Floor:** Level {floor_lvl} — {urgency_label}")

    st.markdown("**Triggered Rules:**")
    for r_id, reason in zip(patient_floor["rule_ids"], patient_floor["reasons"]):
        st.markdown(f"• **{r_id}** — {reason}")

    st.markdown("**Status:**")
    st.markdown(
        f"🔒 **Hard safety floor active.** Future LISA scoring may escalate this patient "
        f"but cannot downgrade them below **Level {floor_lvl}**."
    )
else:
    st.success("**Protocol Floor:** No Hard Floor")
    st.markdown(
        "No hard protocol rule triggered from currently available simulated information.\n\n"
        "_This does NOT mean the patient is safe or low risk. Further risk-of-wait assessment "
        "will be performed by later modules._"
    )
