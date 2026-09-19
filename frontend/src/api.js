/**
 * QuantumFlow REST API helper module.
 */
const BASE_URL = 'http://localhost:8000';

export async function fetchHealth() {
  try {
    const res = await fetch(`${BASE_URL}/api/health`);
    return await res.json();
  } catch (err) {
    console.error('Health fetch error:', err);
    return { status: 'offline', qiskit_available: false, qaoa_backend: 'none' };
  }
}

export async function fetchNetwork() {
  try {
    const res = await fetch(`${BASE_URL}/api/network`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Network fetch error:', err);
    return null;
  }
}

export async function sendControl(payload) {
  try {
    const res = await fetch(`${BASE_URL}/api/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return await res.json();
  } catch (err) {
    console.error('Control error:', err);
    return null;
  }
}

export async function sendEvent(eventData) {
  try {
    const res = await fetch(`${BASE_URL}/api/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(eventData)
    });
    return await res.json();
  } catch (err) {
    console.error('Event injection error:', err);
    return null;
  }
}

export async function fetchLatestBenchmark() {
  try {
    const res = await fetch(`${BASE_URL}/api/benchmark/latest`);
    return await res.json();
  } catch (err) {
    console.error('Benchmark fetch error:', err);
    return null;
  }
}

export async function fetchReplayData() {
  try {
    const res = await fetch('/replay.json');
    return await res.json();
  } catch (err) {
    console.error('Replay fetch error:', err);
    return [];
  }
}
