/**
 * LISA.ai — Nurse Command Center Workstation Controller (Milestone 11B)
 * Manages live queue state, mode toggling, row selection, and panel updates.
 */

(function () {
  const state = {
    mode: 'NORMAL',
    summary: null,
    queue: [],
    selectedPatientToken: null,
    loading: false,
    error: null
  };

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
    renderLoadingState();

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
      renderPlaceholders();
    } catch (err) {
      console.error('Failed to load workstation data:', err);
      state.loading = false;
      state.error = err.message || 'Unable to load LISA simulation data.';
      renderErrorState();
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

    renderPlaceholders();
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

  function renderPlaceholders() {
    const selectedToken = state.selectedPatientToken || '—';
    const patient = state.queue.find(p => p.patient_token === selectedToken);

    // Center Panel Header & Body
    const centerTokenHeader = document.getElementById('selected-token-heading');
    const centerRankChip = document.getElementById('center-rank-chip');
    const centerTierChip = document.getElementById('center-tier-chip');

    if (centerTokenHeader) {
      centerTokenHeader.textContent = selectedToken;
    }
    if (centerRankChip && patient) {
      centerRankChip.textContent = `Rank #${patient.priority_rank}`;
      centerRankChip.style.display = 'inline-flex';
    }
    if (centerTierChip && patient) {
      const tLet = tierLetter(patient.queue_tier_code);
      centerTierChip.textContent = `Tier ${tLet}`;
      centerTierChip.className = `tier tier-${tLet.toLowerCase()}`;
      centerTierChip.style.display = 'inline-block';
    }

    // Right Decision Panel
    const decisionToken = document.getElementById('decision-token');
    if (decisionToken) {
      decisionToken.textContent = selectedToken;
    }
  }

  function renderLoadingState() {
    const listEl = document.getElementById('queue-list');
    if (!listEl) return;
    listEl.innerHTML = `
      <div style="padding: 32px; text-align: center; color: var(--ink-4);">
        <div style="font-size: 13px; font-weight: 500; margin-bottom: 8px;">Loading queue simulation...</div>
      </div>
    `;
  }

  function renderErrorState() {
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
