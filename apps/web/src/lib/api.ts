import axios from 'axios';
import type { JobStatus, MigrationJob, MigrationPlan, MigrationReport, Repository } from '@/types';

export const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export const repositoryApi = {
  list: () => api.get<Repository[]>('/api/repositories'),
  create: (data: { path: string; type: 'git' | 'archive'; url?: string; branch?: string }) =>
    api.post<Repository>('/api/repositories', data),
  get: (id: string) => api.get<Repository>(`/api/repositories/${id}`),
  inspect: (id: string) => api.post<unknown>(`/api/repositories/${id}/inspect`),
  remove: (id: string) => api.delete<{ message: string }>(`/api/repositories/${encodeURIComponent(id)}`),
};

export const migrationApi = {
  listJobs: () => api.get<MigrationJob[]>('/api/migrations/jobs'),
  listPlans: () => api.get<MigrationPlan[]>('/api/migrations/plans'),
  createPlan: (data: { repository_id: string; dependency_name: string; current_version?: string; target_version: string }) =>
    api.post<MigrationPlan>('/api/migrations/plan', data, { timeout: 180000 }),
  getPlan: (id: string) => api.get<MigrationPlan>(`/api/migrations/plan/${id}`),
  start: (planId: string) => api.post<MigrationJob>(`/api/migrations/${planId}/start`),
  getJob: (id: string) => api.get<MigrationJob>(`/api/migrations/job/${id}`),
  getJobStatus: (id: string) => api.get<JobStatus>(`/api/migrations/job/${id}/status`),
  cancel: (id: string) => api.post(`/api/migrations/job/${id}/cancel`),
  getReport: (id: string) => api.get<MigrationReport>(`/api/migrations/job/${id}/report`),
};

export const healthApi = {
  check: (signal?: AbortSignal) =>
    api.get<{ status: string; service: string }>('/health', { signal }),
};