# LISA.ai Demo / Recording Checklist

Use this checklist before recording or presenting the live demo to ensure absolute stability, safety, and compliance with the intended narrative.

## APPLICATION
- [ ] Server running (`streamlit run app.py --server.port 8501`)
- [ ] 120 tests passing (`pytest`)
- [ ] Normal mode (20 Patients) selected initially
- [ ] Audit trail reset (no previous actions lingering)
- [ ] Patient selector combobox working and responsive

## DEMO DATA
- [ ] Patient A125 values verified (Initial Clinician Triage: Level 4, Risk: 35/42/49/63, Tier C)
- [ ] Patient A135 values verified (Clinician Triage: Level 1, Protocol: Level 2, Effective: Level 1, Tier A, Priority #1)
- [ ] Surge mode metrics verified (60 patients, 8 beds, 7.5x patients/bed)
- [ ] Queue Policy Simulation metrics verified (LISA: 0 dynamic-priority inversions)

## INTERACTION
- [ ] Patient A125 override tested successfully
- [ ] Audit event captures the override properly
- [ ] No stale clinician state from previous runs
- [ ] Click "Reset Demo Actions" immediately before starting recording

## RECORDING
- [ ] Browser zoom level appropriate (100% or 110% to ensure readability)
- [ ] Desktop notifications (OS and browser) disabled / Do Not Disturb ON
- [ ] Desktop clean (no distracting tabs, bookmarks, or background wallpapers)
- [ ] Microphone tested and audio levels balanced
- [ ] Resolution set to 1440p or 1080p
- [ ] Mouse cursor visible and highlighting disabled/subtle
- [ ] IDE and terminal completely hidden from view

## SAFETY & MESSAGING
- [ ] Prototype disclaimer ("Prototype simulation only — not for clinical use.") clearly visible
- [ ] No diagnostic language used in speech (do not say "heart attack", "stroke")
- [ ] No treatment claims made
- [ ] No clinical efficacy or mortality reduction claims made (refer only to operational/simulation metrics)

## BACKUP & RESILIENCE
- [ ] Local screenshots available in `screenshots/` directory (final2)
- [ ] Prerecorded video available and accessible locally if the live demo fails
- [ ] Local terminal ready to quickly restart `streamlit run app.py` if needed
