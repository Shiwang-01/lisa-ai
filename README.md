# LISA.ai — Life-saving Intelligent Sequencing Assistant

> **Dynamic ED Sequencing + Deterioration Safety Net**  
> *Prototype simulation only — not for clinical use.*

---

## 📌 Overview

**LISA.ai** is a clinician-controlled emergency department (ED) sequencing prototype designed to assist healthcare providers in identifying waiting patients at risk of deterioration.

- **Traditional Triage Question:** *"How sick is this patient right now?"*
- **LISA's Additional Question:** *"How dangerous could it become for this patient to keep waiting?"*

---

## ⚙️ Milestone 1 Foundation

This repository provides the core foundation:
- 20 realistic simulated emergency department patient presentations (`A124` – `A143`).
- Clean Streamlit dashboard displaying waiting room metrics, full patient roster, and detailed patient cards.
- Strict isolation: zero external APIs, zero LLMs, zero databases, and fully self-contained simulated data.

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Application
```bash
streamlit run app.py
```

---

## 📁 Repository Structure
```
lisa-ai/
├── app.py                  # Main Streamlit dashboard
├── requirements.txt        # Minimal Python dependencies
├── README.md               # Project documentation & disclaimer
├── data/
│   └── seed_patients.csv   # 20 simulated emergency patient records
└── lisa/
    └── __init__.py         # Package initialization
```

---

## ⚠️ Disclaimer
This software is a research and educational prototype simulation only. It is **not** validated for medical diagnosis or clinical decision support.
