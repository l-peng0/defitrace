import type { IncidentListResponse, IncidentBundle, TraceResponse, SourcesResponse } from './types';

const BASE = '';

async function apiFetch<T>(path: string): Promise<T> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(BASE + path, { headers });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export async function fetchIncidents(): Promise<IncidentListResponse> {
  return apiFetch('/api/incidents');
}

export async function fetchBundle(incidentId: string): Promise<IncidentBundle> {
  return apiFetch(`/api/incidents/${incidentId}`);
}

export async function fetchTrace(runId: string): Promise<TraceResponse> {
  return apiFetch(`/api/runs/${runId}/trace`);
}

export async function fetchSources(runId: string): Promise<SourcesResponse> {
  return apiFetch(`/api/runs/${runId}/sources`);
}
