export const duration = (s) => `${Math.floor(s / 60)}m ${s % 60}s`;
export const date = (s) =>
  new Date(
    s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : s + "Z",
  ).toLocaleString();
