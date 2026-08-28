# LISA.ai Final Demo Script

**Target Duration:** 4 minutes 30 seconds
**Core Message:** "Right Patient. Right Bed. Right Time."

---

## 0:00–0:25 — SECTION 1: PROBLEM

**TIME:** 0:00–0:25 (25s)
**SCREEN / ACTION:** Presenter speaks directly to camera or shows title slide.
**EXACT SPEAKER SCRIPT:** "Emergency departments face crowded waiting rooms, limited beds, overloaded clinicians, and incomplete information. The biggest challenge? Patients whose condition may change while waiting. Traditional triage asks: 'How sick is the patient now?' But for operations, the queue itself becomes a clinical risk."
**WHAT THE JUDGE SHOULD NOTICE:** Focus on the operational reality. No exaggerated mortality claims.
**DO NOT SAY:** AI doctor, lives saved, mortality reduction.

---

## 0:25–0:50 — SECTION 2: LISA CONCEPT

**TIME:** 0:25–0:50 (25s)
**SCREEN / ACTION:** Show LISA.ai Normal Operations Dashboard.
**EXACT SPEAKER SCRIPT:** "Traditional triage is a snapshot. LISA adds the dimension of time. It is a clinician-controlled ED sequencing decision-support prototype. It continuously combines clinical safety floors, Risk-of-Wait, reassessment urgency, uncertainty, and existing capacity to recommend who should receive attention next."
**WHAT THE JUDGE SHOULD NOTICE:** Clean, professional dashboard. The disclaimer: "Prototype simulation only — not for clinical use."
**DO NOT SAY:** Diagnosis, prescribe treatment, triage substitute.

---

## 0:50–1:50 — SECTION 3: A125 HERO CASE

**TIME:** 0:50–1:50 (60s)
**SCREEN / ACTION:** Select Patient A125 in the Patient Inspector. Scroll to view Patient Record and Risk of Waiting chart.
**EXACT SPEAKER SCRIPT:** "Let's look at Patient A125. A 68-year-old woman with an ambiguous complaint: gas and upper gastric burning, accompanied by sweating. She has documented diabetes. Her initial clinician triage was Level 4. She has no hard protocol guardrail. A125 has no obvious hard red flag, which is exactly why this case matters. LISA does not diagnose her. Instead, the combination of older age, ambiguous symptom wording, sweating, documented history, and uncertainty increases the simulated risk of leaving her in the queue. Notice her current risk is 35, but jumps to 49 in 60 minutes and 63 in 120 minutes with 82% confidence. Reassessment is due in 15 minutes, placing her in Tier C — Rising Wait-Risk. LISA asks not only how concerning she looks now, but how the risk changes if we keep waiting."
**WHAT THE JUDGE SHOULD NOTICE:** The Risk-of-Wait trajectory chart climbing over time. The absence of diagnostic labels for her symptoms.
**DO NOT SAY:** Heart attack, ischemia, acute coronary syndrome, diagnostic terminology.

---

## 1:50–2:25 — SECTION 4: A135 SAFETY CASE

**TIME:** 1:50–2:25 (35s)
**SCREEN / ACTION:** Select Patient A135. Scroll to Clinical Guardrails and Patient Record.
**EXACT SPEAKER SCRIPT:** "Now consider A135. The clinician has already assigned Level 1. Our automated protocol rule independently identifies a Level 2 safety floor. LISA takes the more urgent safety constraint. The automated system cannot silently downgrade the clinician's Level 1 decision. Her effective Operational Safety Floor remains Level 1, placing her at Priority #1 in Tier A — Immediate Safety Attention. LISA may escalate concern. It cannot override a stronger clinician safety floor."
**WHAT THE JUDGE SHOULD NOTICE:** The visual indicator that the Clinician Triage Level 1 overrides the Level 2 Protocol Guardrail.
**DO NOT SAY:** LISA knows better than the doctor, LISA corrects the doctor.

---

## 2:25–3:05 — SECTION 5: SURGE MODE

**TIME:** 2:25–3:05 (40s)
**SCREEN / ACTION:** Scroll up and toggle Operational Mode to "Surge 3× (60 Patients)". Observe metric updates.
**EXACT SPEAKER SCRIPT:** "We now triple arrivals without adding capacity. There are 60 waiting patients competing for the same 8 ED spaces. We see 7.5 patients per bed and 1 triage nurse model. Reassessments due in under 5 minutes jump to 15, and 23 under 15 minutes. Notice what does NOT change: the patient's clinical inputs and individual risk calculations. What changes is operational competition: rank, reassessment workload, and access to compatible resources."
**WHAT THE JUDGE SHOULD NOTICE:** The restrained amber surge banner. Instant metric recalculation without changing individual patient clinical data.
**DO NOT SAY:** The hospital is failing, patients are dying, red alert.

---

## 3:05–3:35 — SECTION 6: RESOURCE ALLOCATION

**TIME:** 3:05–3:35 (30s)
**SCREEN / ACTION:** Scroll to Recommended Resource Allocation table. Highlight one allocated patient and one awaiting.
**EXACT SPEAKER SCRIPT:** "LISA does not simply give beds to ranks one through eight. It considers resource compatibility. A stable low-acuity injury can use fast-track, preserving monitored or higher-capability resources for patients who need them. Urgency and resource compatibility are different problems."
**WHAT THE JUDGE SHOULD NOTICE:** Clean resource matching. No raw procedural strings presented as allocation recommendations.
**DO NOT SAY:** LISA assigns treatments, LISA orders CT scans.

---

## 3:35–4:00 — SECTION 7: CLINICIAN CONTROL

**TIME:** 3:35–4:00 (25s)
**SCREEN / ACTION:** Return to Patient A125. Open Clinician Override Form. Override to Tier B. Reason: CLINICAL_APPEARANCE. Type optional note. Save. Open Audit Trail.
**EXACT SPEAKER SCRIPT:** "Returning to A125, the system recommends Tier C. If a clinician feels the patient appears more unwell than structured intake suggests, they can override this. We select Tier B and log the reason as Clinical Appearance. The recommendation is preserved. The clinician decision is preserved. And the reason for disagreement is preserved. LISA recommends. The clinician decides. The system remembers why."
**WHAT THE JUDGE SHOULD NOTICE:** The clear distinction between the immutable system recommendation and the authoritative clinician state. The session-scoped audit log.
**DO NOT SAY:** LISA was wrong, the doctor is overriding a mistake.

---

## 4:00–4:20 — SECTION 8: SIMULATION COMPARISON

**TIME:** 4:00–4:20 (20s)
**SCREEN / ACTION:** Open the Queue Policy Simulation expander/section. Focus on dynamic-priority inversions.
**EXACT SPEAKER SCRIPT:** "This is a simulation result, not clinical efficacy evidence. Both policies have exactly the same attention capacity. LISA does not create extra staff capacity. It changes which patients receive scarce attention first. Notice that the static baseline suffers from dynamic-priority inversions, whereas LISA achieves 0 dynamic-priority inversions."
**WHAT THE JUDGE SHOULD NOTICE:** The disclaimer that this is a simulation. The 0 inversions metric.
**DO NOT SAY:** Lives saved, mortality reduction, clinical efficacy proven.

---

## 4:20–4:35 — SECTION 9: GOVERNANCE

**TIME:** 4:20–4:35 (15s)
**SCREEN / ACTION:** Click the Privacy, Safety & Governance tab. Scroll quickly to show Implemented vs Production requirements.
**EXACT SPEAKER SCRIPT:** "We deliberately distinguish what the prototype actually implements from what a production hospital deployment would still require. We use tokenized simulated IDs, guarantee human override, track audit and version histories, and explicitly exclude non-clinical prioritization features. There is no production compliance claim here."
**WHAT THE JUDGE SHOULD NOTICE:** The strict honesty of the side-by-side comparison panels. No fake badges.
**DO NOT SAY:** HIPAA compliant, FDA approved, production-ready.

---

## 4:35–4:45 — SECTION 10: CLOSE

**TIME:** 4:35–4:45 (10s)
**SCREEN / ACTION:** Switch back to the main Operations page.
**EXACT SPEAKER SCRIPT:** "LISA helps emergency teams prioritize not only who is sickest now, but who is most likely to become unsafe if they keep waiting. Right Patient. Right Bed. Right Time."
**WHAT THE JUDGE SHOULD NOTICE:** Final professional view of the operational dashboard.
**DO NOT SAY:** (Anything else, end cleanly).
