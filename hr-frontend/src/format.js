export const COUNTRIES = { IN: "India", US: "United States", GB: "United Kingdom", ALL: "All countries" };

export function scopeLabel(me) {
  const country = COUNTRIES[me.country] || me.country;
  return `${country}, ${me.employment_type.replaceAll("_", " ")}`;
}

// The backend sends times as seconds since 1970.
export function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
