/**
 * LISA.ai — API Client (Milestone 11B)
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
  }
};

window.LISA_API = LISA_API;
