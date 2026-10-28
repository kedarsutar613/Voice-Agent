import axios from "axios";
export const api = axios.create({ baseURL: "/api/v1" });
api.interceptors.request.use((c) => {
  const t = sessionStorage.getItem("token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !e.config.url.includes("/login")) {
      sessionStorage.removeItem("token");
      window.dispatchEvent(new Event("session-expired"));
    }
    return Promise.reject(e);
  },
);
export const errorText = (e) => {
  const d = e.response?.data?.detail;
  return typeof d === "string"
    ? d
    : Array.isArray(d)
      ? d.map((x) => x.msg).join(", ")
      : e.message || "Request failed";
};
