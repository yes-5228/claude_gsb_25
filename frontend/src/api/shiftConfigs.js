import { http } from './client.js';

export const shiftConfigApi = {
  list: () => http.get('/shift-check-configs'),
  get: (shift) => http.get(`/shift-check-configs/${encodeURIComponent(shift)}`),
  update: (shift, payload) => http.put(`/shift-check-configs/${encodeURIComponent(shift)}`, payload),
};
