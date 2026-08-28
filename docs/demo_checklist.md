# LISA.ai Demo / Presentation Checklist

**Release Verified:** `v1.0.0-prototype`  
**Live Demo:** [https://lisa-ai-7dtj.onrender.com/](https://lisa-ai-7dtj.onrender.com/)  
**Primary Workstation:** FastAPI + HTML5 Nurse Command Center  

Use this checklist before recording or presenting the live demo to ensure absolute stability, safety, and narrative compliance.

---

## 🌐 HOSTED DEMO & INFRASTRUCTURE
- [ ] Render service warmed 3–5 minutes before presentation (prevents cold-start latency)
- [ ] Live URL opens: `https://lisa-ai-7dtj.onrender.com/`
- [ ] API health verified (`/api/summary?mode=NORMAL` returns HTTP 200)
- [ ] Command workspace loads initial 20 patients / 8 simulated ED spaces
- [ ] Surge mode toggle tested (loads 60 patients / 8 spaces)
- [ ] "Reset Demo Actions" clicked immediately before presentation
- [ ] Browser hard refresh performed (`Ctrl+F5` or `Cmd+Shift+R`) to clear cache
- [ ] Backup local uvicorn server running ready in background (`uvicorn webapp:app --port 8000`)
- [ ] Backup reference screenshots accessible in `docs/`

---

## 🧪 TESTS & INTEGRITY
- [ ] 134 automated unit and integration tests passing (`pytest`)
- [ ] Zero diff on core backend modules in `lisa/`
- [ ] Datasets in `data/` verified intact and tokenized

---

## 👥 DEMO DATA & WORKSPACE VERIFICATION
- [ ] **Patient A125 Verified:**
  - Initial Clinician Triage: Level 4
  - Risk Trajectory: 35 → 42 → 49 → 63 (Conf: 82%, Recheck: 15m)
  - Tier C / Priority #13
- [ ] **Patient A135 Verified:**
  - Clinician Triage: Level 1
  - Protocol Guardrail: Level 2
  - Effective Safety Floor: Level 1 (Tier A / Priority #1)
- [ ] **Patient A127 Verified:**
  - Low Risk-of-Wait (12) / Tier E / calm state
- [ ] **Capacity Workspace Verified:**
  - 8 simulated ED spaces (B01 Resus, B02-B03 Monitored, B04-B06 General, B07-B08 Fast-track)
  - Awaiting compatible space list populated
- [ ] **Evidence Workspace Verified:**
  - Dynamic priority inversions: Normal 0, Surge 0
  - Disclaimer visible: *"Simulation only — not clinical efficacy evidence."*
- [ ] **Governance Workspace Verified:**
  - Implemented vs. Production requirements panels displayed cleanly

---

## 🎬 RECORDING / SCREEN PRESENTATION
- [ ] Display resolution set to 1440×900 or 1080p (zero horizontal scroll)
- [ ] Browser zoom level set to 100%
- [ ] Desktop notifications & OS sounds muted / Do Not Disturb ON
- [ ] Clean browser window (no bookmarks bar, extraneous tabs, or extensions)
- [ ] Microphone levels balanced and noise suppression enabled
- [ ] Terminal and IDE windows hidden from audience view

---

## 🛡️ CLINICAL SAFETY & PROHIBITED LANGUAGE
- [ ] Disclaimer prominently visible: *"Prototype simulation only — not for clinical use."*
- [ ] **DO NOT SAY:** "AI doctor", "lives saved", "mortality reduction", "clinically proven"
- [ ] **DO NOT USE DIAGNOSTIC TERMS:** Do not say "heart attack", "stroke", "sepsis diagnosis" for complaints
- [ ] **DO NOT MAKE COMPLIANCE CLAIMS:** Do not claim HIPAA, GDPR, DPDP, FDA, or ABDM certification
