import type { TaskPayload } from './types';

const API_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) ||
  '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });

  const data = await response.json();
  if (!response.ok) {
    const message = (data && data.error) || 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

export async function createTask(inputText: string): Promise<{ task_id: string }> {
  return request<{ task_id: string }>('/tasks', {
    method: 'POST',
    body: JSON.stringify({ input_text: inputText }),
  });
}

export async function fetchTask(taskId: string): Promise<TaskPayload> {
  return request<TaskPayload>(`/tasks/${taskId}`);
}
