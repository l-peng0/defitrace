(() => {
  const host = typeof location !== "undefined" ? location.hostname : "";
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  const defaultBase = isLocal ? "http://127.0.0.1:8000" : "";
  window.CAPSTONE_API_BASE = window.CAPSTONE_API_BASE || defaultBase;
})();
