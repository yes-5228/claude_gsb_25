import { http } from './client.js';

export const metaApi = {
  dictionaries: () => http.get('/meta/dictionaries'),
  restroomOptions: (keyword) => http.get('/meta/restroom-options', { keyword }),
  checklists: () => http.get('/meta/checklists'),
  updateChecklist: (shift, items) =>
    http.put(`/meta/checklists/${encodeURIComponent(shift)}`, { items }),
};
