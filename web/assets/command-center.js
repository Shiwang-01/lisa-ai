/**
 * LISA.ai — Nurse Command Center Workstation Controller (Milestones 11B - 11G)
 * Manages live queue state, mode toggling, row selection, selected-patient context,
 * clinician decision actions, override modal, session audit, Capacity, Evidence, and Audit workspaces.
 */

(function () {
  const state = {
    mode: 'NORMAL',
    activeWorkspace: 'command', // 'command' | 'capacity' | 'evidence' | 'audit'
    summary: null,
    queue: [],
    auditEvents: [],
    allocationData: null,
    comparisonData: null,
    selectedPatientToken: null,
    selectedPatientData: null,
    selectedAuditEventId: null,
    auditFilterPatient: '',
    auditFilterAction: '',
    auditFilterMode: '',
    loading: false,
    patientLoading: false,
    capacityLoading: false,
    evidenceLoading: false,
    auditLoading: false,
    actionPending: false,
    feedbackMessage: null,
    feedbackType: null, // 'success' | 'error'
    error: null,
    patientError: null,
    capacityError: null,
    evidenceError: null
  };

  let patientFetchVersion = 0;

  function tierLetter(tierCode) {
    if (!tierCode) return 'E';
    if (tierCode.includes('Tier A')) return 'A';
    if (tierCode.includes('Tier B')) return 'B';
    if (tierCode.includes('Tier C')) return 'C';
    if (tierCode.includes('Tier D')) return 'D';
    if (tierCode.includes('Tier E')) return 'E';
    return tierCode.replace('Tier ', '').trim();
  }

  async function loadData() {
    state.loading = true;
    state.error = null;
    renderQueueLoadingState();

    try {
      const [summary, queue, auditRes, allocRes, compRes] = await Promise.all([
        window.LISA_API.getSummary(state.mode),
        window.LISA_API.getQueue(state.mode),
        window.LISA_API.getAudit().catch(() => ({ events: [] })),
        window.LISA_API.getAllocation(state.mode).catch(() => null),
        window.LISA_API.getComparison(state.mode).catch(() => null)
      ]);

      state.summary = summary;
      state.queue = queue;
      state.auditEvents = auditRes.events || [];
      state.allocationData = allocRes;
      state.comparisonData = compRes;

      // Preserve selection if token exists in new queue, else select first patient
      const tokenExists = queue.some(p => p.patient_token === state.selectedPatientToken);
      if (!tokenExists) {
        state.selectedPatientToken = queue.length > 0 ? queue[0].patient_token : null;
      }

      state.loading = false;
      renderHeader();
      renderQueue();

      if (state.activeWorkspace === 'capacity') {
        renderCapacityWorkspace();
      } else if (state.activeWorkspace === 'evidence') {
        renderEvidenceWorkspace();
      } else if (state.activeWorkspace === 'audit') {
        renderAuditWorkspace();
      } else {
        if (state.selectedPatientToken) {
          fetchAndRenderPatient(state.selectedPatientToken);
        } else {
          renderEmptyPatientState();
          renderEmptyDecisionState();
        }
      }
    } catch (err) {
      console.error('Failed to load workstation data:', err);
      state.loading = false;
      state.error = err.message || 'Unable to load LISA simulation data.';
      renderQueueErrorState();
    }
  }

  function setMode(newMode) {
    if (state.mode === newMode && !state.error) return;
    state.mode = newMode;
    document.body.dataset.mode = newMode;
    state.feedbackMessage = null;

    // Update active button state
    document.querySelectorAll('.mode-selector button').forEach(btn => {
      if (btn.dataset.mode === newMode) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    loadData();
  }

  function switchWorkspace(workspace) {
    if (state.activeWorkspace === workspace) return;
    state.activeWorkspace = workspace;

    const commandWs = document.getElementById('command-workspace');
    const capacityWs = document.getElementById('capacity-workspace');
    const evidenceWs = document.getElementById('evidence-workspace');
    const auditWs = document.getElementById('audit-workspace');

    document.querySelectorAll('.nav .nav-item').forEach(item => {
      if (item.dataset.nav === workspace) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Hide all
    if (commandWs) commandWs.style.display = 'none';
    if (capacityWs) capacityWs.style.display = 'none';
    if (evidenceWs) evidenceWs.style.display = 'none';
    if (auditWs) auditWs.style.display = 'none';

    if (workspace === 'capacity') {
      if (capacityWs) {
        capacityWs.style.display = 'grid';
        renderCapacityWorkspace();
      }
    } else if (workspace === 'evidence') {
      if (evidenceWs) {
        evidenceWs.style.display = 'grid';
        renderEvidenceWorkspace();
      }
    } else if (workspace === 'audit') {
      if (auditWs) {
        auditWs.style.display = 'grid';
        renderAuditWorkspace();
      }
    } else {
      if (commandWs) {
        commandWs.style.display = 'grid';
        if (state.selectedPatientToken) {
          fetchAndRenderPatient(state.selectedPatientToken);
        }
      }
    }
  }

  function selectPatient(token) {
    if (state.selectedPatientToken === token && state.selectedPatientData) return;
    state.selectedPatientToken = token;
    state.feedbackMessage = null;

    // Highlight row in list
    document.querySelectorAll('#queue-list .qrow').forEach(row => {
      if (row.dataset.token === token) {
        row.classList.add('selected');
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        row.classList.remove('selected');
      }
    });

    // Update right decision panel token preview
    const decisionToken = document.getElementById('decision-token');
    if (decisionToken) decisionToken.textContent = token;

    fetchAndRenderPatient(token);
  }

  function selectPatientAndSwitchToCommand(token) {
    switchWorkspace('command');
    selectPatient(token);
  }

  async function fetchAndRenderPatient(token) {
    const fetchId = ++patientFetchVersion;
    state.patientLoading = true;
    state.patientError = null;
    renderPatientLoadingSkeleton(token);

    try {
      const data = await window.LISA_API.getPatient(token, state.mode);
      if (fetchId !== patientFetchVersion) return; // Stale response guard

      state.selectedPatientData = data;
      state.patientLoading = false;
      renderSelectedPatient(data);
      renderDecisionPanel(data);
    } catch (err) {
      if (fetchId !== patientFetchVersion) return;
      console.error(`Failed to fetch patient ${token}:`, err);
      state.patientLoading = false;
      state.patientError = err.message || 'Unable to load selected patient.';
      renderPatientErrorState(token);
    }
  }

  async function refreshAudit() {
    try {
      const auditRes = await window.LISA_API.getAudit();
      state.auditEvents = auditRes.events || [];
      if (state.activeWorkspace === 'audit') {
        renderAuditWorkspace();
      }
    } catch (err) {
      console.warn('Failed to refresh audit log:', err);
    }
  }

  function renderHeader() {
    if (!state.summary) return;
    const s = state.summary;
    const isSurge = state.mode === 'SURGE_3X';

    const waitingEl = document.getElementById('metric-waiting');
    const spacesEl = document.getElementById('metric-spaces');
    const reassess5El = document.getElementById('metric-reassess5');
    const avgWaitEl = document.getElementById('metric-avgwait');

    if (waitingEl) {
      waitingEl.textContent = s.patient_count;
      waitingEl.className = `v ${isSurge ? 'warn' : ''}`;
    }
    if (spacesEl) {
      spacesEl.textContent = s.bed_count;
    }
    if (reassess5El) {
      reassess5El.textContent = s.reassess_within_5_min;
      reassess5El.className = `v ${isSurge || s.reassess_within_5_min > 10 ? 'warn' : ''}`;
    }
    if (avgWaitEl) {
      avgWaitEl.textContent = `${s.avg_wait_min}m`;
    }
  }

  function renderQueue() {
    const listEl = document.getElementById('queue-list');
    const countEl = document.getElementById('queue-count');
    if (!listEl) return;

    if (countEl) {
      countEl.textContent = state.queue.length;
    }

    if (state.queue.length === 0) {
      listEl.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--ink-3);">
          No patients waiting in queue.
        </div>
      `;
      return;
    }

    const rowsHtml = state.queue.map(p => {
      const isSelected = p.patient_token === state.selectedPatientToken;
      const tLet = tierLetter(p.queue_tier_code);
      const isRising = p.risk_60_min >= 65;
      const isRisingMid = p.risk_60_min >= 45 && p.risk_60_min < 65;
      const riskCls = isRising ? 'rising' : (isRisingMid ? 'rising-mid' : '');
      const isUrgent = p.recheck_due_min <= 5;
      const reCls = isUrgent ? 'urgent' : '';

      return `
        <div class="qrow ${isSelected ? 'selected' : ''}" 
             data-token="${p.patient_token}" 
             data-tier="${p.queue_tier_code}"
             tabindex="0"
             role="button"
             aria-pressed="${isSelected}">
          <div class="r-rank mono">#${p.priority_rank}</div>
          <div class="r-token">${p.patient_token}</div>
          <div class="r-demo">${p.age}${p.sex ? p.sex.charAt(0) : ''}</div>
          <div class="r-complaint" title="${p.complaint_text}">${p.complaint_text}</div>
          <div class="r-tier">
            <span class="tier tier-${tLet.toLowerCase()}">${tLet}</span>
          </div>
          <div class="r-risk ${riskCls} mono">
            <span class="now">${p.current_risk}</span>
            <span class="arrow">→</span>
            <span class="next">${p.risk_60_min}</span>
          </div>
          <div class="r-wait mono">${p.arrival_minutes_ago}m</div>
          <div class="r-re ${reCls} mono">
            <span class="dot"></span>
            <span class="t">${p.recheck_due_min}m</span>
          </div>
        </div>
      `;
    }).join('');

    listEl.innerHTML = rowsHtml;

    listEl.querySelectorAll('.qrow').forEach(row => {
      row.addEventListener('click', () => {
        selectPatient(row.dataset.token);
      });
      row.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectPatient(row.dataset.token);
        }
      });
    });
  }

  function renderTrajectorySvg(current, r30, r60, r120) {
    const W = 320, H = 54, padX = 14, padY = 8;
    const values = [current, r30, r60, r120];
    const minVal = 0, maxVal = 100;

    const stepX = (W - padX * 2) / 3;
    const pts = values.map((v, i) => {
      const x = padX + i * stepX;
      const y = H - padY - ((v - minVal) / (maxVal - minVal)) * (H - padY * 2);
      return [x, y];
    });

    const pathD = pts.map((p, i) => (i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`)).join(' ');
    const areaD = `${pathD} L ${pts[3][0]} ${H - padY} L ${pts[0][0]} ${H - padY} Z`;

    const y75 = H - padY - ((75 - minVal) / (maxVal - minVal)) * (H - padY * 2);

    const circles = pts.map((p, i) => {
      const isPeak = i === 3;
      return `<circle cx="${p[0]}" cy="${p[1]}" r="${isPeak ? 3 : 2.2}" fill="${isPeak ? '#4F46E5' : '#fff'}" stroke="#4F46E5" stroke-width="1.5" />`;
    }).join('');

    return `
      <svg viewBox="0 0 ${W} ${H}" class="risk-svg-container" preserveAspectRatio="none">
        <defs>
          <linearGradient id="risk-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#4F46E5" stop-opacity="0.2"/>
            <stop offset="100%" stop-color="#4F46E5" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        <line x1="${padX}" y1="${y75}" x2="${W - padX}" y2="${y75}" stroke="#FDA29B" stroke-width="1" stroke-dasharray="3,3" />
        <text x="${W - padX - 18}" y="${y75 - 2}" font-size="8" fill="#B42318" font-family="var(--ff-mono)" font-weight="600">75</text>
        <path d="${areaD}" fill="url(#risk-grad)" />
        <path d="${pathD}" fill="none" stroke="#4F46E5" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
        ${circles}
      </svg>
    `;
  }

  function renderSelectedPatient(data) {
    const container = document.getElementById('selected-patient-container');
    if (!container) return;

    const p = data.patient;
    const g = data.guardrails;
    const r = data.risk_of_wait;
    const q = data.queue;

    const centerRankChip = document.getElementById('center-rank-chip');
    const centerTierChip = document.getElementById('center-tier-chip');
    if (centerRankChip) {
      centerRankChip.textContent = `Rank #${q.priority_rank}`;
      centerRankChip.style.display = 'inline-flex';
    }
    if (centerTierChip) {
      const tLet = tierLetter(q.queue_tier_code);
      centerTierChip.textContent = `Tier ${tLet}`;
      centerTierChip.className = `tier tier-${tLet.toLowerCase()}`;
      centerTierChip.style.display = 'inline-block';
    }

    const bpStr = (p.systolic_bp && p.diastolic_bp) ? `${p.systolic_bp}/${p.diastolic_bp}` : '—';
    const spo2Str = p.spo2 ? `${p.spo2}%` : '—';
    const tempStr = p.temperature ? `${p.temperature}°` : '—';
    const hrStr = p.heart_rate ?? '—';
    const rrStr = p.respiratory_rate ?? '—';

    let safetyHtml = '';
    if (g.has_hard_floor) {
      const sourceNote = (g.effective_safety_floor_source === 'CLINICIAN_TRIAGE')
        ? 'Clinician triage takes precedence'
        : (g.reasons && g.reasons.length > 0 ? g.reasons[0] : 'Protocol rule triggered');

      safetyHtml = `
        <div class="safety-lock-banner">
          <div class="safety-lock-hdr">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
            Operational Safety Floor Engaged
          </div>
          <div class="safety-lock-grid">
            <div class="safety-lock-cell">
              <div class="lk">Initial Triage</div>
              <div class="lv">Level ${g.initial_triage_level ?? '—'}</div>
              <div class="note">Clinician</div>
            </div>
            <div class="safety-lock-cell">
              <div class="lk">Protocol Floor</div>
              <div class="lv">Level ${g.protocol_floor_level ?? '—'}</div>
              <div class="note">LISA Rule</div>
            </div>
            <div class="safety-lock-cell effective-lock">
              <div class="lk">Effective Floor</div>
              <div class="lv">Level ${g.effective_safety_floor}</div>
              <div class="note">${sourceNote}</div>
            </div>
          </div>
        </div>
      `;
    } else {
      const protoLabel = g.triggered ? `Level ${g.floor_level}` : 'No Hard Floor';
      safetyHtml = `
        <div class="safety-neutral-grid">
          <div class="safety-neutral-cell">
            <div class="sk">Initial Clinician Triage</div>
            <div class="sv">Level ${g.initial_triage_level ?? '—'}</div>
          </div>
          <div class="safety-neutral-cell">
            <div class="sk">Protocol Guardrail</div>
            <div class="sv">${protoLabel}</div>
          </div>
        </div>
      `;
    }

    const isUrgentRecheck = r.recheck_due_min <= 5;
    const recheckCls = isUrgentRecheck ? 'urgent' : '';
    const safetySubtext = g.has_hard_floor ? `
      <div class="risk-alert-subtext">
        Safety floor active — reassessment urgency takes precedence over waiting projections.
      </div>
    ` : '';

    const svgChart = renderTrajectorySvg(r.current_risk, r.risk_30_min, r.risk_60_min, r.risk_120_min);

    const rawReasons = [];
    if (g.has_hard_floor && g.reasons && g.reasons.length > 0) {
      rawReasons.push({ text: `Safety floor active: ${g.reasons[0]}`, isGuardrail: true });
    }
    if (q.sequence_reasons) {
      q.sequence_reasons.forEach(sr => rawReasons.push({ text: sr, isGuardrail: false }));
    }
    if (r.risk_factors) {
      r.risk_factors.slice(0, 3).forEach(rf => rawReasons.push({ text: rf, isGuardrail: false }));
    }
    if (r.uncertainty_factors && r.uncertainty_factors.length > 0) {
      rawReasons.push({ text: r.uncertainty_factors[0], isGuardrail: false });
    }

    const seen = new Set();
    const primaryReasons = [];
    for (const item of rawReasons) {
      const key = item.text.toLowerCase().slice(0, 30);
      if (!seen.has(key)) {
        seen.add(key);
        primaryReasons.push(item);
        if (primaryReasons.length >= 4) break;
      }
    }

    const reasonsHtml = primaryReasons.map(rItem => `
      <div class="factor-item">
        <span class="factor-bullet ${rItem.isGuardrail ? 'guardrail' : ''}"></span>
        <span>${rItem.text}</span>
      </div>
    `).join('');

    const historyHtml = p.known_history ? `
      <div class="pat-history-row">
        <span class="hk">History:</span>
        <span class="hv" title="${p.known_history}">${p.known_history}</span>
      </div>
    ` : '';

    container.innerHTML = `
      <div class="pat-hdr-block">
        <div class="pat-token-row">
          <span class="token">${p.patient_token}</span>
          <span class="demo">${p.age}${p.sex ? p.sex.charAt(0) : ''}</span>
          <span class="sep">·</span>
          <span class="wait">${p.arrival_minutes_ago}m waiting</span>
        </div>
        <div class="pat-complaint-box">
          "${p.complaint_text}"
        </div>
      </div>

      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Vitals</span>
          <div class="line"></div>
        </div>
        <div class="vitals-grid">
          <div class="vital-cell"><span class="vk">HR</span><span class="vv">${hrStr}</span></div>
          <div class="vital-cell"><span class="vk">BP</span><span class="vv">${bpStr}</span></div>
          <div class="vital-cell"><span class="vk">SpO2</span><span class="vv">${spo2Str}</span></div>
          <div class="vital-cell"><span class="vk">RR</span><span class="vv">${rrStr}</span></div>
          <div class="vital-cell"><span class="vk">Temp</span><span class="vv">${tempStr}</span></div>
        </div>
      </div>

      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Safety</span>
          <div class="line"></div>
        </div>
        ${safetyHtml}
      </div>

      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Simulated Risk of Waiting</span>
          <div class="line"></div>
          <span class="aux">0–120 min horizon</span>
        </div>
        <div class="risk-block">
          ${safetySubtext}
          <div class="risk-numbers-row">
            <div class="risk-trajectory-nums">
              <span class="now">${r.current_risk}</span>
              <span class="arr">→</span>
              <span>${r.risk_30_min}</span>
              <span class="arr">→</span>
              <span>${r.risk_60_min}</span>
              <span class="arr">→</span>
              <span class="peak">${r.risk_120_min}</span>
            </div>
            <div class="risk-meta-pills">
              <div class="pill">
                <span class="pk">Confidence:</span>
                <span class="pv">${r.confidence}%</span>
              </div>
              <div class="pill">
                <span class="pk">Reassess:</span>
                <span class="pv ${recheckCls}">${r.recheck_due_min} min</span>
              </div>
            </div>
          </div>
          ${svgChart}
        </div>
      </div>

      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Contributing Factors</span>
          <div class="line"></div>
        </div>
        <div class="factors-list">
          ${reasonsHtml}
        </div>
      </div>

      ${historyHtml}
    `;
  }

  // =========================================================================
  // RIGHT PANEL: DECISION ENGINE & CLINICIAN ACTIONS (Milestone 11D)
  // =========================================================================

  function renderDecisionPanel(data) {
    const container = document.getElementById('decision-container');
    if (!container) return;

    const p = data.patient;
    const g = data.guardrails;
    const r = data.risk_of_wait;
    const q = data.queue;
    const res = data.resource;

    const patientEvents = state.auditEvents.filter(e => e.patient_token === p.patient_token);
    const latestEvent = patientEvents.length > 0 ? patientEvents[patientEvents.length - 1] : null;

    let clinicianStateHtml = '<div class="d-clin-state-val">System recommendation active</div>';
    if (latestEvent) {
      if (latestEvent.action === 'ACCEPT') {
        clinicianStateHtml = `
          <div class="d-clin-state-val accepted">
            <b>Accepted</b> (${latestEvent.clinician_selected_tier || latestEvent.system_queue_tier})
          </div>
        `;
      } else if (latestEvent.action === 'ESCALATE') {
        clinicianStateHtml = `
          <div class="d-clin-state-val escalated">
            <b>Escalated:</b> ${latestEvent.system_queue_tier} → ${latestEvent.clinician_selected_tier}
          </div>
        `;
      } else if (latestEvent.action === 'OVERRIDE') {
        const rName = (latestEvent.override_reason || '').replace(/_/g, ' ');
        clinicianStateHtml = `
          <div class="d-clin-state-val override">
            <b>Override Active:</b> ${latestEvent.system_queue_tier} → ${latestEvent.clinician_selected_tier}
            <div style="font-size:10.5px; color:#B54708; margin-top:2px; font-weight:500;">
              Reason: ${rName}
            </div>
          </div>
        `;
      }
    }

    const safetyLockNote = g.has_hard_floor ? `
      <div class="d-safety-indicator">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
        Level ${g.effective_safety_floor} safety floor active
      </div>
    ` : '';

    const isUrgent = r.recheck_due_min <= 5;
    const reassessText = `Reassess in ${r.recheck_due_min} min`;

    let resBadgeHtml = '';
    let resTitle = 'Awaiting Bed';
    let resNote = 'Queue position maintained on priority';

    if (res && res.bed_id) {
      resTitle = `${res.bed_id} — ${res.bed_type || 'General'}`;
      resBadgeHtml = '<span class="d-res-badge avail">ALLOCATED</span>';
      resNote = res.compatibility_note || 'Assigned to compatible bed space';
    } else {
      resTitle = 'Awaiting Suitable Bed';
      resBadgeHtml = '<span class="d-res-badge hold">HOLD</span>';
      resNote = (res && res.compatibility_note) ? res.compatibility_note : 'No immediate space; priority queue active';
    }

    const feedbackHtml = state.feedbackMessage ? `
      <div class="d-feedback ${state.feedbackType || 'success'}">
        <span>${state.feedbackMessage}</span>
      </div>
    ` : '';

    let recentActionsHtml = '<div class="d-recent-empty">No clinician actions recorded this session.</div>';
    if (patientEvents.length > 0) {
      const displayEvents = patientEvents.slice(-2).reverse();
      recentActionsHtml = displayEvents.map(e => {
        const timeStr = e.timestamp ? e.timestamp.split('T')[1].split('.')[0] : '';
        const actLabel = e.action === 'OVERRIDE' ? 'Override' : (e.action === 'ESCALATE' ? 'Escalate' : 'Accept');
        const transition = (e.system_queue_tier && e.clinician_selected_tier)
          ? `${e.system_queue_tier} → ${e.clinician_selected_tier}`
          : (e.system_queue_tier || '');
        const rSub = e.override_reason
          ? `<div class="ri-desc">${e.override_reason.replace(/_/g, ' ')} · ${e.user_role}</div>`
          : `<div class="ri-desc">${e.user_role} · ${e.operational_mode || ''}</div>`;

        return `
          <div class="d-recent-item">
            <div class="ri-top">
              <span>${actLabel} · ${transition}</span>
              <span style="font-size:9.5px; color:var(--ink-4); font-family:var(--ff-mono);">${timeStr}</span>
            </div>
            ${rSub}
          </div>
        `;
      }).join('');
    }

    container.innerHTML = `
      <div class="d-sys-card">
        <div class="d-lbl">System Recommendation</div>
        <div class="d-sys-tier-row">
          <div class="d-sys-tier">${q.queue_tier_code}</div>
          <div style="font-size:12px; font-weight:700; font-family:var(--ff-mono); color:var(--ink-3);">#${q.priority_rank}</div>
        </div>
        <div class="d-sys-metrics">
          <div class="m-item"><span class="mk">Score:</span><span class="mv">${q.priority_score ?? '—'}</span></div>
          <div class="m-item"><span class="mk">Conf:</span><span class="mv">${r.confidence}%</span></div>
        </div>
      </div>

      <div class="d-reassess-box">
        <span class="rk">Reassess</span>
        <span class="rv ${isUrgent ? 'urgent' : ''}">${reassessText}</span>
      </div>

      <div class="d-res-box">
        <div class="rk">Resource Allocation</div>
        <div class="d-res-row">
          <span class="d-res-bed">${resTitle}</span>
          ${resBadgeHtml}
        </div>
        <div class="d-res-note">${resNote}</div>
      </div>

      <div class="d-clin-section">
        <div class="d-clin-hdr">
          <span class="title">Your Decision</span>
          ${safetyLockNote}
        </div>

        ${clinicianStateHtml}
        ${feedbackHtml}

        <div class="d-btn-group">
          <button class="d-btn d-btn-accept" id="btn-action-accept" ${state.actionPending ? 'disabled' : ''}>
            <span>Accept Recommendation</span>
            <span class="shortcut">✓</span>
          </button>
          <button class="d-btn d-btn-escalate" id="btn-action-escalate" ${state.actionPending ? 'disabled' : ''}>
            <span>Escalate Priority</span>
            <span class="shortcut">⚡</span>
          </button>
          <button class="d-btn d-btn-override" id="btn-action-override" ${state.actionPending ? 'disabled' : ''}>
            <span>Override System Tier...</span>
            <span class="shortcut">⚙</span>
          </button>
        </div>
      </div>

      <div class="d-recent-sect">
        <div class="d-recent-hdr">
          <span>Recent Session Action</span>
          <span style="font-size:9px; font-weight:500; text-transform:none; color:var(--ink-4);">${p.patient_token}</span>
        </div>
        <div class="d-recent-list">
          ${recentActionsHtml}
        </div>
      </div>

      <div class="d-reset-wrap">
        <button class="btn-reset-actions" id="btn-reset-session-actions">Reset Demo Actions</button>
      </div>
    `;

    const btnAccept = document.getElementById('btn-action-accept');
    const btnEscalate = document.getElementById('btn-action-escalate');
    const btnOverride = document.getElementById('btn-action-override');
    const btnReset = document.getElementById('btn-reset-session-actions');

    if (btnAccept) {
      btnAccept.addEventListener('click', () => handleAccept(p.patient_token));
    }
    if (btnEscalate) {
      btnEscalate.addEventListener('click', () => handleEscalate(p.patient_token));
    }
    if (btnOverride) {
      btnOverride.addEventListener('click', () => handleOpenOverrideModal(data));
    }
    if (btnReset) {
      btnReset.addEventListener('click', handleResetAudit);
    }
  }

  async function handleAccept(token) {
    if (state.actionPending) return;
    state.actionPending = true;
    state.feedbackMessage = null;
    renderDecisionPanel(state.selectedPatientData);

    try {
      const res = await window.LISA_API.acceptAction(token, state.mode);
      state.feedbackMessage = 'Decision recorded: Accepted recommendation';
      state.feedbackType = 'success';
      await refreshAudit();
    } catch (err) {
      state.feedbackMessage = err.message || 'Failed to record accept action';
      state.feedbackType = 'error';
    } finally {
      state.actionPending = false;
      renderDecisionPanel(state.selectedPatientData);
    }
  }

  async function handleEscalate(token) {
    if (state.actionPending) return;
    state.actionPending = true;
    state.feedbackMessage = null;
    renderDecisionPanel(state.selectedPatientData);

    try {
      const res = await window.LISA_API.escalateAction(token, state.mode);
      state.feedbackMessage = `Priority escalated to ${res.event?.clinician_selected_tier || 'higher tier'}`;
      state.feedbackType = 'success';
      await refreshAudit();
    } catch (err) {
      state.feedbackMessage = err.message || 'Failed to record escalation';
      state.feedbackType = 'error';
    } finally {
      state.actionPending = false;
      renderDecisionPanel(state.selectedPatientData);
    }
  }

  function handleOpenOverrideModal(data) {
    const modalRoot = document.getElementById('modal-root');
    if (!modalRoot) return;

    const p = data.patient;
    const g = data.guardrails;
    const q = data.queue;

    const safetyText = g.has_hard_floor
      ? `Active Level ${g.effective_safety_floor} Safety Floor`
      : 'No Active Safety Floor';

    modalRoot.innerHTML = `
      <div class="modal-overlay" id="override-modal-overlay">
        <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-hdr">
            <div class="m-title" id="modal-title">Override System Recommendation · ${p.patient_token}</div>
            <button class="m-close" id="btn-modal-close" aria-label="Close">×</button>
          </div>
          <div class="modal-body">
            <div class="modal-info-strip">
              <div><b>System Tier:</b> ${q.queue_tier_code}</div>
              <div><b>Floor:</b> ${safetyText}</div>
            </div>

            <div id="modal-error-container"></div>

            <div class="modal-form-group">
              <label for="override-target-tier">Target Operational Tier</label>
              <select id="override-target-tier">
                <option value="Tier A">Tier A (Immediate / Critical)</option>
                <option value="Tier B">Tier B (Emergent / High Risk)</option>
                <option value="Tier C" selected>Tier C (Urgent / Rising Risk)</option>
                <option value="Tier D">Tier D (Less Urgent / Moderate)</option>
                <option value="Tier E">Tier E (Non-Urgent / Stable)</option>
              </select>
            </div>

            <div class="modal-form-group">
              <label for="override-reason">Override Reason</label>
              <select id="override-reason">
                <option value="CLINICAL_APPEARANCE">Clinical Appearance</option>
                <option value="NEW_INFORMATION">New Clinical Information</option>
                <option value="PATIENT_DETERIORATION">Acute Patient Deterioration</option>
                <option value="RESOURCE_CONSTRAINT">Operational / Space Constraint</option>
                <option value="CLINICIAN_JUDGMENT">Senior Clinician Judgment</option>
                <option value="OTHER">Other Specified</option>
              </select>
            </div>

            <div class="modal-form-group">
              <label for="override-note">Clinical Justification / Note (Optional)</label>
              <textarea id="override-note" rows="2" placeholder="Document specific rationale..."></textarea>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-modal-cancel" id="btn-modal-cancel">Cancel</button>
            <button class="btn-modal-submit" id="btn-modal-submit">Record Override</button>
          </div>
        </div>
      </div>
    `;

    const targetSelect = document.getElementById('override-target-tier');
    if (targetSelect && q.queue_tier_code) {
      if (q.queue_tier_code.includes('Tier A')) targetSelect.value = 'Tier B';
      else if (q.queue_tier_code.includes('Tier B')) targetSelect.value = 'Tier A';
      else if (q.queue_tier_code.includes('Tier C')) targetSelect.value = 'Tier B';
      else if (q.queue_tier_code.includes('Tier D')) targetSelect.value = 'Tier C';
      else if (q.queue_tier_code.includes('Tier E')) targetSelect.value = 'Tier D';
    }

    function closeModal() {
      modalRoot.innerHTML = '';
    }

    document.getElementById('btn-modal-close').addEventListener('click', closeModal);
    document.getElementById('btn-modal-cancel').addEventListener('click', closeModal);
    document.getElementById('override-modal-overlay').addEventListener('click', (e) => {
      if (e.target.id === 'override-modal-overlay') closeModal();
    });

    document.getElementById('btn-modal-submit').addEventListener('click', async () => {
      const targetTier = document.getElementById('override-target-tier').value;
      const reason = document.getElementById('override-reason').value;
      const note = document.getElementById('override-note').value;
      const submitBtn = document.getElementById('btn-modal-submit');
      const errBox = document.getElementById('modal-error-container');

      submitBtn.disabled = true;
      errBox.innerHTML = '';

      try {
        await window.LISA_API.overrideAction(p.patient_token, targetTier, reason, note, state.mode);
        closeModal();
        state.feedbackMessage = `Override recorded: ${targetTier}`;
        state.feedbackType = 'success';
        await refreshAudit();
        renderDecisionPanel(state.selectedPatientData);
      } catch (err) {
        submitBtn.disabled = false;
        errBox.innerHTML = `
          <div class="modal-err-box">
            <b>Override Blocked:</b> ${err.detail || err.message}
          </div>
        `;
      }
    });
  }

  async function handleResetAudit() {
    if (!confirm('Reset all clinician action events for this prototype session?')) return;
    try {
      await window.LISA_API.resetAudit();
      state.auditEvents = [];
      state.selectedAuditEventId = null;
      state.feedbackMessage = 'Session decisions reset';
      state.feedbackType = 'success';
      if (state.selectedPatientData) {
        renderDecisionPanel(state.selectedPatientData);
      }
      if (state.activeWorkspace === 'audit') {
        renderAuditWorkspace();
      }
    } catch (err) {
      alert(`Failed to reset audit: ${err.message}`);
    }
  }

  // =========================================================================
  // CAPACITY WORKSPACE CONTROLLER (Milestone 11E)
  // =========================================================================

  async function renderCapacityWorkspace() {
    const container = document.getElementById('capacity-workspace');
    if (!container) return;

    if (!state.allocationData) {
      try {
        state.allocationData = await window.LISA_API.getAllocation(state.mode);
      } catch (err) {
        container.innerHTML = `
          <div class="state-banner error" style="grid-column: span 2;">
            <span><b>Unable to load simulated resource assignments.</b></span>
            <button id="btn-retry-capacity">Retry</button>
          </div>
        `;
        const btn = document.getElementById('btn-retry-capacity');
        if (btn) btn.addEventListener('click', renderCapacityWorkspace);
        return;
      }
    }

    const alloc = state.allocationData;
    const beds = alloc.beds || [];
    const allocations = alloc.allocations || [];
    const waitingPatients = alloc.waiting_patients || [];

    const awaitingSuitable = waitingPatients.filter(p => p.allocation_status === 'WAITING_SUITABLE_BED');
    const awaitingGeneralQueue = waitingPatients.filter(p => p.allocation_status === 'WAITING_QUEUE');

    const cardsHtml = beds.map(b => {
      const pAlloc = allocations.find(a => a.bed_id === b.bed_id);
      const bType = (b.bed_type || 'general').toLowerCase().replace(' ', '-');
      const hasPatient = !!b.recommended_patient;
      const patToken = b.recommended_patient || (pAlloc ? pAlloc.patient_token : null);
      const patRank = b.priority_rank || (pAlloc ? pAlloc.priority_rank : null);
      const patTier = b.queue_tier || (pAlloc ? pAlloc.queue_tier_code : null);
      const tLet = tierLetter(patTier);
      const riskStr = (pAlloc && pAlloc.current_risk != null && pAlloc.risk_60_min != null)
        ? `${pAlloc.current_risk} → ${pAlloc.risk_60_min}`
        : '';
      const whyText = b.why || (pAlloc ? (pAlloc.allocation_reasons?.[0] || pAlloc.allocation_reason) : 'Compatible space assignment');

      return `
        <div class="cap-card ${hasPatient ? '' : 'unassigned'}" 
             data-token="${patToken || ''}" 
             tabindex="0"
             role="button"
             aria-label="${b.bed_id} ${b.bed_type} ${hasPatient ? 'Allocated to ' + patToken : 'Unassigned'}">
          <div class="cap-card-top">
            <span class="cap-bed-id">${b.bed_id}</span>
            <span class="cap-bed-type ${bType}">${b.bed_type}</span>
          </div>

          <div class="cap-card-patient">
            ${hasPatient ? `
              <div class="cap-pat-row-1">
                <span class="cap-pat-token">${patToken}</span>
                <span class="cap-pat-rank">Rank #${patRank}</span>
              </div>
              <div class="cap-pat-row-2">
                <span class="tier tier-${tLet.toLowerCase()}">Tier ${tLet}</span>
                ${riskStr ? `<span class="cap-pat-risk mono">${riskStr}</span>` : ''}
              </div>
            ` : `
              <div>UNASSIGNED</div>
            `}
          </div>

          <div class="cap-card-note" title="${whyText}">
            ${whyText}
          </div>
        </div>
      `;
    }).join('');

    let awaitingListHtml = '<div class="awaiting-empty">No patients currently awaiting a compatible simulated resource.</div>';
    if (awaitingSuitable.length > 0) {
      awaitingListHtml = awaitingSuitable.map(p => {
        const tLet = tierLetter(p.queue_tier_code);
        const reqStr = (p.acceptable_bed_types && p.acceptable_bed_types.length > 0)
          ? p.acceptable_bed_types.join(', ')
          : (p.preferred_bed_types?.join(', ') || 'Monitored / Resus');
        const reasonText = p.allocation_reasons?.[0] || p.allocation_reason || 'Requires higher-capability placement';
        const isUrgent = p.recheck_due_min <= 5;

        return `
          <div class="awaiting-card" data-token="${p.patient_token}" tabindex="0" role="button">
            <div class="awaiting-top">
              <span class="awaiting-token">${p.patient_token}</span>
              <span class="awaiting-recheck mono ${isUrgent ? 'urgent' : ''}">
                Reassess ${p.recheck_due_min}m
              </span>
            </div>
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <span class="cap-pat-rank">Rank #${p.priority_rank}</span>
              <span class="tier tier-${tLet.toLowerCase()}">Tier ${tLet}</span>
            </div>
            <div class="awaiting-req">Compatible: ${reqStr}</div>
            <div class="awaiting-reason">${reasonText}</div>
          </div>
        `;
      }).join('');
    }

    container.innerHTML = `
      <section class="cap-main-panel" aria-label="Simulated ED Resources">
        <div class="p-hdr">
          <div class="title">Simulated ED Spaces</div>
          <div class="sub">8 Total Simulated Resources · Deterministic prototype placement</div>
          <div class="spacer"></div>
          <div class="cap-hdr-stats">
            <span class="c-stat">Allocated: <b>${beds.filter(b => b.recommended_patient).length} / ${beds.length}</b></span>
            <span class="c-stat ${awaitingSuitable.length > 0 ? 'warn' : ''}">Awaiting Suitable: <b>${awaitingSuitable.length}</b></span>
            <span class="c-stat">General Queue: <b>${awaitingGeneralQueue.length}</b></span>
          </div>
        </div>

        <div class="cap-grid-container">
          ${cardsHtml}
        </div>
      </section>

      <section class="cap-awaiting-panel" aria-label="Awaiting Suitable Capacity">
        <div class="p-hdr">
          <div class="title">Awaiting Suitable Capacity</div>
          <div class="spacer"></div>
          <span class="chip" style="font-weight:700;">${awaitingSuitable.length} Patients</span>
        </div>

        <div class="awaiting-list scroll">
          ${awaitingListHtml}
        </div>
      </section>
    `;

    container.querySelectorAll('.cap-card[data-token], .awaiting-card[data-token]').forEach(el => {
      const token = el.dataset.token;
      if (token) {
        el.addEventListener('click', () => selectPatientAndSwitchToCommand(token));
        el.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            selectPatientAndSwitchToCommand(token);
          }
        });
      }
    });
  }

  // =========================================================================
  // EVIDENCE / POLICY SIMULATION WORKSPACE (Milestone 11F)
  // =========================================================================

  async function renderEvidenceWorkspace() {
    const container = document.getElementById('evidence-workspace');
    if (!container) return;

    if (!state.comparisonData) {
      try {
        state.comparisonData = await window.LISA_API.getComparison(state.mode);
      } catch (err) {
        container.innerHTML = `
          <div class="state-banner error" style="grid-column: span 2;">
            <span><b>Unable to load policy simulation.</b></span>
            <button id="btn-retry-evidence">Retry</button>
          </div>
        `;
        const btn = document.getElementById('btn-retry-evidence');
        if (btn) btn.addEventListener('click', renderEvidenceWorkspace);
        return;
      }
    }

    const comp = state.comparisonData.comparison || {};
    const assump = comp.simulation_assumptions || {
      simulation_horizon_min: 120,
      attention_slot_min: 5,
      triage_nurses: 1,
      available_attention_slots: 24,
      patient_count: state.mode === 'SURGE_3X' ? 60 : 20
    };
    const sBase = comp.static_baseline || {};
    const lisa = comp.lisa || {};

    container.innerHTML = `
      <section class="ev-main-panel" aria-label="Policy Simulation Comparison">
        <div class="ev-disclaimer-banner">
          <div class="ev-disclaimer-left">
            <span class="ev-badge">Simulation Result</span>
            <span class="ev-disclaimer-text">Not clinical efficacy evidence · Evaluates sequencing order under identical attention capacity</span>
          </div>
          <div class="ev-capacity-chip">
            SAME ATTENTION CAPACITY (${assump.available_attention_slots} slots · ${assump.simulation_horizon_min}m horizon)
          </div>
        </div>

        <div class="ev-metrics-body">
          <div class="ev-policy-headers">
            <div class="ev-policy-card">
              <div class="ev-policy-title">
                <span>Static Baseline Policy</span>
                <span style="font-size:9.5px; font-weight:600; color:var(--ink-4);">STANDARD SIMULATION</span>
              </div>
              <div class="ev-policy-sub">Initial Clinician Triage + First-In First-Out within triage level</div>
            </div>
            <div class="ev-policy-card lisa-card">
              <div class="ev-policy-title">
                <span>LISA Sequencing Policy</span>
                <span style="font-size:9.5px; font-weight:700; color:var(--primary);">DYNAMIC PROTOCOL</span>
              </div>
              <div class="ev-policy-sub">Protocol Floors + Risk-of-Wait Trajectory + Reassessment Urgency</div>
            </div>
          </div>

          <div class="ev-hero-metric highlight">
            <div class="ev-hero-top">
              <span class="ev-hero-title">Dynamic Priority Inversions</span>
              <span class="chip" style="font-weight:700; color:var(--primary);">PRIMARY OPERATIONAL METRIC</span>
            </div>
            <div class="ev-hero-desc">
              A dynamic-priority inversion occurs when a patient with greater current operational urgency is attended after a lower-priority patient under the simulated policy.
            </div>
            <div class="ev-hero-values">
              <div class="ev-hero-val-card">
                <span class="lbl">Static Baseline</span>
                <span class="val">${sBase.lower_urgency_ahead_of_urgent_count ?? '—'}</span>
              </div>
              <div class="ev-hero-val-card lisa">
                <span class="lbl">LISA Dynamic Policy</span>
                <span class="val">${lisa.lower_urgency_ahead_of_urgent_count ?? '0'}</span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">High Wait-Risk Patients Reviewed ≤ 30 min</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">Risk-of-Wait ≥ 65</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.high_wait_risk_reviewed_within_30_min ?? '—'} / ${sBase.high_wait_risk_total ?? '—'} (${sBase.high_wait_risk_reviewed_pct ?? '—'}%)</span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.high_wait_risk_reviewed_within_30_min ?? '—'} / ${lisa.high_wait_risk_total ?? '—'} (${lisa.high_wait_risk_reviewed_pct ?? '—'}%)</span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">Average Reassessment Delay</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">Minutes past deadline</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.average_reassessment_delay_min ?? '—'} min <span style="font-size:9.5px; font-weight:400; color:var(--ink-3);">(med ${sBase.median_reassessment_delay_min ?? '—'}m)</span></span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.average_reassessment_delay_min ?? '—'} min <span style="font-size:9.5px; font-weight:400; color:var(--ink-3);">(med ${lisa.median_reassessment_delay_min ?? '—'}m)</span></span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">Reassessment Deadlines Missed</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">Simulated capacity breach</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.reassessment_deadlines_missed ?? '—'} / ${assump.patient_count} (${sBase.reassessment_deadlines_missed_pct ?? '—'}%)</span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.reassessment_deadlines_missed ?? '—'} / ${assump.patient_count} (${lisa.reassessment_deadlines_missed_pct ?? '—'}%)</span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">Urgent Patients Reviewed ≤ 15 min</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">Tier A & Tier B cohort</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.urgent_reviewed_within_15_min ?? '—'} / ${sBase.urgent_total ?? '—'} (${sBase.urgent_reviewed_pct ?? '—'}%)</span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.urgent_reviewed_within_15_min ?? '—'} / ${lisa.urgent_total ?? '—'} (${lisa.urgent_reviewed_pct ?? '—'}%)</span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">Protocol-Floor Patients Reviewed ≤ 5 min</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">Level 1 & 2 floors</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.protocol_floor_reviewed_within_5_min ?? '—'} / ${sBase.protocol_floor_total ?? '—'} (${sBase.protocol_floor_reviewed_pct ?? '—'}%)</span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.protocol_floor_reviewed_within_5_min ?? '—'} / ${lisa.protocol_floor_total ?? '—'} (${lisa.protocol_floor_reviewed_pct ?? '—'}%)</span>
              </div>
            </div>
          </div>

          <div class="ev-row-item">
            <div class="ev-row-hdr">
              <span class="ev-row-label">120-Minute Horizon Attention Coverage</span>
              <span style="font-size:10px; color:var(--ink-4); font-family:var(--ff-mono);">24 available 5m slots</span>
            </div>
            <div class="ev-row-values">
              <div class="ev-val-box">
                <span>Static</span>
                <span class="val-num">${sBase.reviewed_within_horizon ?? '—'} reviewed (${sBase.not_reviewed_within_horizon ?? '0'} unreviewed)</span>
              </div>
              <div class="ev-val-box lisa">
                <span>LISA</span>
                <span class="val-num">${lisa.reviewed_within_horizon ?? '—'} reviewed (${lisa.not_reviewed_within_horizon ?? '0'} unreviewed)</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside class="ev-side-panel">
        <div class="ev-side-card">
          <div class="ev-side-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            What the Simulation Suggests
          </div>
          <ul class="ev-bullet-list">
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot primary"></span>
              <span>LISA dynamically shifts the priority sequence under identical attention capacity.</span>
            </li>
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot primary"></span>
              <span>Dynamic sequencing eliminates simulated priority inversions in this cohort.</span>
            </li>
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot primary"></span>
              <span>Under surge pressure, physical attention capacity limits dominate both policies.</span>
            </li>
          </ul>
        </div>

        <div class="ev-side-card" style="border-left: 3px solid #F79009;">
          <div class="ev-side-title" style="color:#B54708;">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#B54708" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            What This Does NOT Prove
          </div>
          <ul class="ev-bullet-list">
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot" style="background:#B54708;"></span>
              <span>Not prospective clinical validation or real-world patient trial.</span>
            </li>
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot" style="background:#B54708;"></span>
              <span>Not clinical efficacy evidence or outcome guarantee.</span>
            </li>
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot" style="background:#B54708;"></span>
              <span>Uses simulated patient cohort and simplified staffing assumptions.</span>
            </li>
            <li class="ev-bullet-item">
              <span class="ev-bullet-dot" style="background:#B54708;"></span>
              <span>Requires clinical validation and institutional approval before deployment.</span>
            </li>
          </ul>
        </div>

        <div class="ev-side-card">
          <div class="ev-side-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Simulation Assumptions
          </div>
          <div class="ev-assump-grid">
            <div class="ev-assump-cell">
              <div class="ev-assump-k">Horizon</div>
              <div class="ev-assump-v">${assump.simulation_horizon_min} min</div>
            </div>
            <div class="ev-assump-cell">
              <div class="ev-assump-k">Slot Length</div>
              <div class="ev-assump-v">${assump.attention_slot_min} min</div>
            </div>
            <div class="ev-assump-cell">
              <div class="ev-assump-k">Triage Nurses</div>
              <div class="ev-assump-v">${assump.triage_nurses} Nurse</div>
            </div>
            <div class="ev-assump-cell">
              <div class="ev-assump-k">Available Slots</div>
              <div class="ev-assump-v">${assump.available_attention_slots} Slots</div>
            </div>
            <div class="ev-assump-cell" style="grid-column: span 2;">
              <div class="ev-assump-k">Capacity Invariant</div>
              <div class="ev-assump-v" style="font-size:10px; font-weight:600; color:var(--ink-2);">
                Identical resources modeled across both policies
              </div>
            </div>
          </div>
        </div>
      </aside>
    `;
  }

  // =========================================================================
  // AUDIT WORKSPACE CONTROLLER (Milestone 11G)
  // =========================================================================

  async function renderAuditWorkspace() {
    const container = document.getElementById('audit-workspace');
    if (!container) return;

    try {
      const auditRes = await window.LISA_API.getAudit();
      state.auditEvents = auditRes.events || [];
    } catch (err) {
      container.innerHTML = `
        <div class="state-banner error" style="grid-column: span 2;">
          <span><b>Unable to load clinician audit trail.</b></span>
          <button id="btn-retry-audit">Retry</button>
        </div>
      `;
      const btn = document.getElementById('btn-retry-audit');
      if (btn) btn.addEventListener('click', renderAuditWorkspace);
      return;
    }

    const allEvents = state.auditEvents;

    // Apply Client-Side Filters
    let filteredEvents = allEvents;
    if (state.auditFilterPatient) {
      filteredEvents = filteredEvents.filter(e => e.patient_token.toLowerCase().includes(state.auditFilterPatient.toLowerCase()));
    }
    if (state.auditFilterAction) {
      filteredEvents = filteredEvents.filter(e => e.action === state.auditFilterAction);
    }
    if (state.auditFilterMode) {
      filteredEvents = filteredEvents.filter(e => e.operational_mode === state.auditFilterMode);
    }

    // Auto-select first event if none selected or selected is missing
    const selectedEvent = allEvents.find(e => e.event_id === state.selectedAuditEventId) || (filteredEvents.length > 0 ? filteredEvents[0] : null);
    if (selectedEvent) {
      state.selectedAuditEventId = selectedEvent.event_id;
    } else {
      state.selectedAuditEventId = null;
    }

    // Unique patient tokens for filter suggestion
    const uniqueTokens = Array.from(new Set(allEvents.map(e => e.patient_token)));

    // Table rows HTML
    let tableBodyHtml = '';
    if (allEvents.length === 0) {
      tableBodyHtml = `
        <tr>
          <td colspan="6">
            <div class="aud-empty">
              <div class="aud-empty-title">No clinician actions recorded in this session.</div>
              <div class="aud-empty-sub">Accept, escalate, or override a system recommendation in Command to create an audit event.</div>
            </div>
          </td>
        </tr>
      `;
    } else if (filteredEvents.length === 0) {
      tableBodyHtml = `
        <tr>
          <td colspan="6">
            <div class="aud-empty">
              <div class="aud-empty-title">No events match the selected filters.</div>
              <div class="aud-empty-sub">Try clearing or adjusting your patient, action, or mode filters.</div>
            </div>
          </td>
        </tr>
      `;
    } else {
      tableBodyHtml = filteredEvents.map(e => {
        const isSelected = e.event_id === state.selectedAuditEventId;
        const timeStr = e.timestamp ? e.timestamp.split('T')[1].split('.')[0] : '—';
        const actLower = e.action.toLowerCase();
        const modeLabel = e.operational_mode === 'SURGE_3X' ? 'Surge 3×' : 'Normal';

        let transitionText = '';
        if (e.action === 'ACCEPT') {
          transitionText = `${e.system_queue_tier} <span style="color:var(--ink-4); font-size:10px;">(Accepted)</span>`;
        } else {
          transitionText = `${e.system_queue_tier} → <b>${e.clinician_selected_tier || '—'}</b>`;
        }

        const reasonText = (e.override_reason || '—').replace(/_/g, ' ');

        return `
          <tr class="aud-row ${isSelected ? 'selected' : ''}" data-id="${e.event_id}">
            <td class="mono" style="color:var(--ink-3); font-size:10px;">${timeStr}</td>
            <td class="mono" style="font-weight:700; color:var(--primary); font-size:11.5px;">${e.patient_token}</td>
            <td><span class="aud-badge ${actLower}">${e.action}</span></td>
            <td>${transitionText}</td>
            <td style="color:var(--ink-2);">${reasonText}</td>
            <td style="font-size:10px; color:var(--ink-3);">${modeLabel}</td>
          </tr>
        `;
      }).join('');
    }

    // Detail Panel HTML
    let detailHtml = '';
    if (!selectedEvent) {
      detailHtml = `
        <div class="aud-empty" style="margin-top:40px;">
          <div class="aud-empty-title">No Event Selected</div>
          <div class="aud-empty-sub">Select an audit event from the list to view the immutable decision snapshot.</div>
        </div>
      `;
    } else {
      const e = selectedEvent;
      const timeStr = e.timestamp ? e.timestamp.replace('T', ' ').split('.')[0] : '—';
      const reasonLabel = (e.override_reason || 'None specified').replace(/_/g, ' ');
      const protoFloorStr = e.protocol_floor_level ? `Level ${e.protocol_floor_level}` : 'No Hard Floor';
      const effFloorStr = e.effective_safety_floor ? `Level ${e.effective_safety_floor}` : 'None';
      const bedStr = e.system_bed_id ? `${e.system_bed_id} (${e.system_bed_type || 'General'})` : 'None / Awaiting';

      detailHtml = `
        <!-- 1. Event Metadata -->
        <div class="aud-detail-sect">
          <div class="aud-detail-sect-title">
            <span>Event Identification</span>
            <span class="mono" style="font-size:9.5px; font-weight:600; color:var(--primary);">${e.event_id.slice(0, 8)}...</span>
          </div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">Timestamp</div><div class="aud-v mono">${timeStr}</div></div>
            <div class="aud-cell"><div class="aud-k">User Role</div><div class="aud-v">${e.user_role || 'TRIAGE_NURSE_01'}</div></div>
            <div class="aud-cell"><div class="aud-k">Patient Token</div><div class="aud-v mono" style="color:var(--primary); font-size:12px;">${e.patient_token}</div></div>
            <div class="aud-cell"><div class="aud-k">Operational Mode</div><div class="aud-v">${e.operational_mode}</div></div>
          </div>
        </div>

        <!-- 2. Clinician Decision -->
        <div class="aud-detail-sect" style="border-color:#C7D7FE; background:#F8FAFF;">
          <div class="aud-detail-sect-title" style="color:var(--primary);">
            <span>Clinician Decision</span>
            <span class="aud-badge ${e.action.toLowerCase()}">${e.action}</span>
          </div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">Action Taken</div><div class="aud-v">${e.action}</div></div>
            <div class="aud-cell"><div class="aud-k">Clinician Tier</div><div class="aud-v" style="color:var(--primary);">${e.clinician_selected_tier || e.system_queue_tier}</div></div>
            <div class="aud-cell" style="grid-column: span 2;"><div class="aud-k">Reason</div><div class="aud-v">${reasonLabel}</div></div>
          </div>
          ${e.override_note ? `
            <div class="aud-note-box">
              "${e.override_note}"
            </div>
          ` : ''}
        </div>

        <!-- 3. System Snapshot at Event Time -->
        <div class="aud-detail-sect">
          <div class="aud-detail-sect-title"><span>System Recommendation Snapshot</span></div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">System Tier</div><div class="aud-v">${e.system_queue_tier}</div></div>
            <div class="aud-cell"><div class="aud-k">Priority Rank</div><div class="aud-v mono">#${e.system_queue_rank ?? '—'}</div></div>
            <div class="aud-cell"><div class="aud-k">Sequence Score</div><div class="aud-v mono">${e.system_sequence_score ?? '—'}</div></div>
            <div class="aud-cell"><div class="aud-k">Resource Status</div><div class="aud-v">${e.system_resource_status ?? '—'}</div></div>
          </div>
        </div>

        <!-- 4. Safety Context -->
        <div class="aud-detail-sect">
          <div class="aud-detail-sect-title"><span>Safety Floor Context</span></div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">Initial Clinician Triage</div><div class="aud-v">Level ${e.initial_triage_level ?? '—'}</div></div>
            <div class="aud-cell"><div class="aud-k">Protocol Floor</div><div class="aud-v">${protoFloorStr}</div></div>
            <div class="aud-cell" style="grid-column: span 2;"><div class="aud-k">Effective Safety Floor</div><div class="aud-v" style="color:${e.effective_safety_floor ? 'var(--danger)' : 'var(--ink)'};">${effFloorStr}</div></div>
          </div>
        </div>

        <!-- 5. Risk Context -->
        <div class="aud-detail-sect">
          <div class="aud-detail-sect-title"><span>Risk of Waiting Snapshot</span></div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">Current Risk</div><div class="aud-v mono">${e.current_risk ?? '—'}/100</div></div>
            <div class="aud-cell"><div class="aud-k">60-Min Projected Risk</div><div class="aud-v mono">${e.risk_60_min ?? '—'}/100</div></div>
            <div class="aud-cell"><div class="aud-k">Model Confidence</div><div class="aud-v">${e.confidence ?? '—'}%</div></div>
            <div class="aud-cell"><div class="aud-k">Reassessment Due</div><div class="aud-v">${e.recheck_due_min ?? '—'} min</div></div>
          </div>
        </div>

        <!-- 6. Version Trace -->
        <div class="aud-detail-sect">
          <div class="aud-detail-sect-title"><span>Immutable Engine Version Trace</span></div>
          <div class="aud-grid-2">
            <div class="aud-cell"><div class="aud-k">Risk Model</div><div class="aud-v mono" style="font-size:10px;">${e.model_version || 'LISA-RoW-v0.7'}</div></div>
            <div class="aud-cell"><div class="aud-k">Rule Set</div><div class="aud-v mono" style="font-size:10px;">${e.rule_version || 'LISA-Demo-Rules-v1'}</div></div>
            <div class="aud-cell" style="grid-column: span 2;"><div class="aud-k">Sequencer Engine</div><div class="aud-v mono" style="font-size:10px;">${e.sequencer_version || 'LISA-SEQ-v1'}</div></div>
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <!-- LEFT: AUDIT EVENTS TABLE -->
      <section class="aud-main-panel" aria-label="Session Clinician Audit Log">
        <div class="p-hdr">
          <div class="title">Session Clinician Audit</div>
          <div class="sub">Prototype session log of clinician decisions · <span id="audit-event-count">${allEvents.length}</span> recorded</div>
          <div class="spacer"></div>
          <span class="chip mono" style="font-size:10.5px;">User: TRIAGE_NURSE_01</span>
        </div>

        <!-- Filter Controls -->
        <div class="aud-filter-bar">
          <div class="aud-filter-group">
            <label for="aud-sel-patient">Patient:</label>
            <select id="aud-sel-patient" class="aud-filter-select">
              <option value="">All Patients</option>
              ${uniqueTokens.map(tok => `<option value="${tok}" ${state.auditFilterPatient === tok ? 'selected' : ''}>${tok}</option>`).join('')}
            </select>
          </div>

          <div class="aud-filter-group">
            <label for="aud-sel-action">Action:</label>
            <select id="aud-sel-action" class="aud-filter-select">
              <option value="" ${state.auditFilterAction === '' ? 'selected' : ''}>All Actions</option>
              <option value="ACCEPT" ${state.auditFilterAction === 'ACCEPT' ? 'selected' : ''}>ACCEPT</option>
              <option value="ESCALATE" ${state.auditFilterAction === 'ESCALATE' ? 'selected' : ''}>ESCALATE</option>
              <option value="OVERRIDE" ${state.auditFilterAction === 'OVERRIDE' ? 'selected' : ''}>OVERRIDE</option>
            </select>
          </div>

          <div class="aud-filter-group">
            <label for="aud-sel-mode">Mode:</label>
            <select id="aud-sel-mode" class="aud-filter-select">
              <option value="" ${state.auditFilterMode === '' ? 'selected' : ''}>All Modes</option>
              <option value="NORMAL" ${state.auditFilterMode === 'NORMAL' ? 'selected' : ''}>Normal</option>
              <option value="SURGE_3X" ${state.auditFilterMode === 'SURGE_3X' ? 'selected' : ''}>Surge 3×</option>
            </select>
          </div>

          <button class="aud-btn-reset" id="btn-reset-audit-workspace">Reset Demo Actions</button>
        </div>

        <!-- Table Container -->
        <div class="aud-table-container scroll">
          <table class="aud-table">
            <thead>
              <tr>
                <th style="width:75px;">Time</th>
                <th style="width:65px;">Patient</th>
                <th style="width:85px;">Action</th>
                <th>Decision Transition</th>
                <th>Reason</th>
                <th style="width:75px;">Mode</th>
              </tr>
            </thead>
            <tbody id="aud-table-body">
              ${tableBodyHtml}
            </tbody>
          </table>
        </div>
      </section>

      <!-- RIGHT: DETAIL INSPECTOR -->
      <section class="aud-detail-panel" aria-label="Audit Event Inspector">
        <div class="p-hdr">
          <div class="title">Audit Event Inspector</div>
          <div class="spacer"></div>
          ${selectedEvent ? `
            <button class="btn-open-command" id="btn-open-in-command" data-token="${selectedEvent.patient_token}">
              Open in Command ↗
            </button>
          ` : ''}
        </div>

        <div class="aud-detail-body scroll">
          ${detailHtml}
        </div>
      </section>
    `;

    // Attach Listeners
    const selPatient = document.getElementById('aud-sel-patient');
    const selAction = document.getElementById('aud-sel-action');
    const selMode = document.getElementById('aud-sel-mode');
    const btnReset = document.getElementById('btn-reset-audit-workspace');
    const btnOpenCmd = document.getElementById('btn-open-in-command');

    if (selPatient) {
      selPatient.addEventListener('change', (e) => {
        state.auditFilterPatient = e.target.value;
        renderAuditWorkspace();
      });
    }
    if (selAction) {
      selAction.addEventListener('change', (e) => {
        state.auditFilterAction = e.target.value;
        renderAuditWorkspace();
      });
    }
    if (selMode) {
      selMode.addEventListener('change', (e) => {
        state.auditFilterMode = e.target.value;
        renderAuditWorkspace();
      });
    }
    if (btnReset) {
      btnReset.addEventListener('click', handleResetAudit);
    }
    if (btnOpenCmd) {
      btnOpenCmd.addEventListener('click', () => {
        const tok = btnOpenCmd.dataset.token;
        if (tok) selectPatientAndSwitchToCommand(tok);
      });
    }

    container.querySelectorAll('.aud-row[data-id]').forEach(row => {
      row.addEventListener('click', () => {
        state.selectedAuditEventId = row.dataset.id;
        renderAuditWorkspace();
      });
    });
  }

  function renderPatientLoadingSkeleton(token) {
    const container = document.getElementById('selected-patient-container');
    if (!container) return;
    container.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--ink-4);">
        <div style="font-size: 13px; font-weight: 600; color: var(--ink-2); margin-bottom: 6px;">Loading Patient ${token}...</div>
        <div style="font-size: 11.5px;">Fetching clinical profile and Risk-of-Wait trajectory.</div>
      </div>
    `;
  }

  function renderPatientErrorState(token) {
    const container = document.getElementById('selected-patient-container');
    if (!container) return;
    container.innerHTML = `
      <div class="state-banner error">
        <span><b>Unable to load patient ${token}.</b></span>
        <button id="btn-retry-patient">Retry</button>
      </div>
    `;
    const btnRetry = document.getElementById('btn-retry-patient');
    if (btnRetry) {
      btnRetry.addEventListener('click', () => fetchAndRenderPatient(token));
    }
  }

  function renderEmptyPatientState() {
    const container = document.getElementById('selected-patient-container');
    if (!container) return;
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--ink-4);">
        Select a patient from the queue to view clinical context.
      </div>
    `;
  }

  function renderEmptyDecisionState() {
    const container = document.getElementById('decision-container');
    if (!container) return;
    container.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--ink-4);">
        Select a patient from the queue to record decisions.
      </div>
    `;
  }

  function renderQueueLoadingState() {
    const listEl = document.getElementById('queue-list');
    if (!listEl) return;
    listEl.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--ink-4);">
        <div style="font-size: 13px; font-weight: 500;">Loading queue simulation...</div>
      </div>
    `;
  }

  function renderQueueErrorState() {
    const listEl = document.getElementById('queue-list');
    if (!listEl) return;
    listEl.innerHTML = `
      <div class="state-banner error">
        <span><b>Unable to load LISA simulation data.</b> (${state.error})</span>
        <button id="btn-retry-load">Retry</button>
      </div>
    `;
    const btnRetry = document.getElementById('btn-retry-load');
    if (btnRetry) {
      btnRetry.addEventListener('click', () => loadData());
    }
  }

  function initScale() {
    const app = document.querySelector('.app');
    if (!app) return;
    const W = 1440, H = 900;
    function fit() {
      const vw = window.innerWidth, vh = window.innerHeight;
      const s = Math.min(vw / W, vh / H, 1);
      app.style.transform = `scale(${s})`;
    }
    fit();
    window.addEventListener('resize', fit);
  }

  function init() {
    initScale();

    // Mode toggle buttons
    document.querySelectorAll('.mode-selector button').forEach(btn => {
      btn.addEventListener('click', () => {
        setMode(btn.dataset.mode);
      });
    });

    // Navigation rail buttons
    document.querySelectorAll('.nav .nav-item:not(.disabled)').forEach(item => {
      item.addEventListener('click', () => {
        const nav = item.dataset.nav;
        if (nav === 'command' || nav === 'capacity' || nav === 'evidence' || nav === 'audit') {
          switchWorkspace(nav);
        }
      });
    });

    // Initial load
    loadData();
  }

  window.LISA_WORKSTATION = { init, setMode, selectPatient, switchWorkspace, renderAuditWorkspace };

  document.addEventListener('DOMContentLoaded', init);
})();
