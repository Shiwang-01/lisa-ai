/**
 * LISA.ai — Nurse Command Center Workstation Controller (Milestone 11C)
 * Manages live queue state, mode toggling, row selection, and selected-patient clinical context.
 */

(function () {
  const state = {
    mode: 'NORMAL',
    summary: null,
    queue: [],
    selectedPatientToken: null,
    selectedPatientData: null,
    loading: false,
    patientLoading: false,
    error: null,
    patientError: null
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
      const [summary, queue] = await Promise.all([
        window.LISA_API.getSummary(state.mode),
        window.LISA_API.getQueue(state.mode)
      ]);

      state.summary = summary;
      state.queue = queue;

      // Preserve selection if token exists in new queue, else select first patient
      const tokenExists = queue.some(p => p.patient_token === state.selectedPatientToken);
      if (!tokenExists) {
        state.selectedPatientToken = queue.length > 0 ? queue[0].patient_token : null;
      }

      state.loading = false;
      renderHeader();
      renderQueue();

      if (state.selectedPatientToken) {
        fetchAndRenderPatient(state.selectedPatientToken);
      } else {
        renderEmptyPatientState();
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

  function selectPatient(token) {
    if (state.selectedPatientToken === token && state.selectedPatientData) return;
    state.selectedPatientToken = token;

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
    } catch (err) {
      if (fetchId !== patientFetchVersion) return;
      console.error(`Failed to fetch patient ${token}:`, err);
      state.patientLoading = false;
      state.patientError = err.message || 'Unable to load selected patient.';
      renderPatientErrorState(token);
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

    // Attach click and keyboard listeners
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

  // Generates lightweight SVG trajectory chart
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

    // 75 Threshold line
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
        <!-- Threshold 75 line -->
        <line x1="${padX}" y1="${y75}" x2="${W - padX}" y2="${y75}" stroke="#FDA29B" stroke-width="1" stroke-dasharray="3,3" />
        <text x="${W - padX - 18}" y="${y75 - 2}" font-size="8" fill="#B42318" font-family="var(--ff-mono)" font-weight="600">75</text>
        <!-- Area & line -->
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

    // Update center panel header chips
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

    // Vitals formatted values
    const bpStr = (p.systolic_bp && p.diastolic_bp) ? `${p.systolic_bp}/${p.diastolic_bp}` : '—';
    const spo2Str = p.spo2 ? `${p.spo2}%` : '—';
    const tempStr = p.temperature ? `${p.temperature}°` : '—';
    const hrStr = p.heart_rate ?? '—';
    const rrStr = p.respiratory_rate ?? '—';

    // Safety Section formatting
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

    // Risk of Waiting Trajectory & Meta
    const isUrgentRecheck = r.recheck_due_min <= 5;
    const recheckCls = isUrgentRecheck ? 'urgent' : '';
    const safetySubtext = g.has_hard_floor ? `
      <div class="risk-alert-subtext">
        Safety floor active — reassessment urgency takes precedence over waiting projections.
      </div>
    ` : '';

    const svgChart = renderTrajectorySvg(r.current_risk, r.risk_30_min, r.risk_60_min, r.risk_120_min);

    // Filter and deduplicate contributing reasons (max 4-5)
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

    // Deduplicate by text lowercase prefix
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

    // History line
    const historyHtml = p.known_history ? `
      <div class="pat-history-row">
        <span class="hk">History:</span>
        <span class="hv" title="${p.known_history}">${p.known_history}</span>
      </div>
    ` : '';

    container.innerHTML = `
      <!-- Header -->
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

      <!-- 1. Vitals -->
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

      <!-- 2. Safety -->
      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Safety</span>
          <div class="line"></div>
        </div>
        ${safetyHtml}
      </div>

      <!-- 3. Risk of Waiting -->
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

      <!-- 4. Contributing Factors -->
      <div class="c-sect">
        <div class="c-sect-hdr">
          <span>Contributing Factors</span>
          <div class="line"></div>
        </div>
        <div class="factors-list">
          ${reasonsHtml}
        </div>
      </div>

      <!-- 5. History Note -->
      ${historyHtml}
    `;
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

  // Scale the workstation cleanly to fit the viewport without page scrolling
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

    // Initial load
    loadData();
  }

  window.LISA_WORKSTATION = { init, setMode, selectPatient };

  document.addEventListener('DOMContentLoaded', init);
})();
