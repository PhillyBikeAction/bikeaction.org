import Fuse from 'fuse.js';
import * as PPAFormData from './ppa-form-data.json';

export function get_fields() {
  return Object.keys(PPAFormData);
}

export function get_options(field: string) {
  return Object.entries(PPAFormData).find(
    ([key]) => key === field,
  )?.[1] as readonly string[];
}

export function best_match(field: string, userValue: string) {
  const fuse = new Fuse(get_options(field));
  return fuse.search(userValue)[0].item;
}
