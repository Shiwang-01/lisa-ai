/**
 * LISA.ai — API Client (Milestones 11B, 11C, 11D)
 * Centralized fetch adapter for LISA FastAPI endpoints.
 */
const LISA_API = {
  baseUrl: '/api',

  async getStatus() {
    const res = await fetch(`${this.baseUrl}/status`);
    if (!res.ok) throw new Error(`Status API failed: ${res.status}`);
    return await res.json();
  },

  async getSummary(mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/summary?mode=${encodeURIComponent(mode)}`);
    if (!res.ok) throw new Error(`Summary API failed: ${res.status}`);
    return await res.json();
  },

  async getQueue(mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/queue?mode=${encodeURIComponent(mode)}`);
    if (!res.ok) throw new Error(`Queue API failed: ${res.status}`);
    return await res.json();
  },

  async getPatient(patientToken, mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/patient/${encodeURIComponent(patientToken)}?mode=${encodeURIComponent(mode)}`);
    if (!res.ok) throw new Error(`Patient API failed: ${res.status}`);
    return await res.json();
  },

  async getAllocation(mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/allocation?mode=${encodeURIComponent(mode)}`);
    if (!res.ok) throw new Error(`Allocation API failed: ${res.status}`);
    return await res.json();
  },

  async getAudit() {
    const res = await fetch(`${this.baseUrl}/audit`);
    if (!res.ok) throw new Error(`Audit API failed: ${res.status}`);
    return await res.json();
  },

  async getComparison(mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/comparison?mode=${encodeURIComponent(mode)}`);
    if (!res.ok) throw new Error(`Comparison API failed: ${res.status}`);
    return await res.json();
  },

  async acceptAction(patientToken, mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/actions/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_token: patientToken, mode: mode, user_role: 'TRIAGE_NURSE_01' })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Accept action failed: ${res.status}`);
    }
    return data;
  },

  async escalateAction(patientToken, mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/actions/escalate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_token: patientToken, mode: mode, user_role: 'TRIAGE_NURSE_01' })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Escalate action failed: ${res.status}`);
    }
    return data;
  },

  async overrideAction(patientToken, targetTier, reason, note = '', mode = 'NORMAL') {
    const res = await fetch(`${this.baseUrl}/actions/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_token: patientToken,
        target_tier: targetTier,
        reason: reason,
        note: note,
        mode: mode,
        user_role: 'TRIAGE_NURSE_01'
      })
    });
    const data = await res.json();
    if (!res.ok) {
      const error = new Error(data.detail || `Override failed: ${res.status}`);
      error.status = res.status;
      error.detail = data.detail;
      throw error;
    }
    return data;
  },

  async resetAudit() {
    const res = await fetch(`${this.baseUrl}/audit/reset`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(`Reset audit failed: ${res.status}`);
    return await res.json();
  }
};

window.LISA_API = LISA_API;
