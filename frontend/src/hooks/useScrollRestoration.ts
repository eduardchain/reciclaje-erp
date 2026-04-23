import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

const SCROLLER_ID = "main-scroll";

export function saveScroll(url: string) {
  const el = document.getElementById(SCROLLER_ID);
  if (!el) return;
  if (el.scrollTop > 0) sessionStorage.setItem(`scroll:${url}`, String(el.scrollTop));
  else sessionStorage.removeItem(`scroll:${url}`);
}

export function useScrollRestoration(ready = true) {
  const location = useLocation();
  const key = `scroll:${location.pathname}${location.search}`;
  const restoredRef = useRef(false);

  useEffect(() => {
    if (!ready || restoredRef.current) return;
    const saved = sessionStorage.getItem(key);
    if (!saved) return;
    restoredRef.current = true;
    const el = document.getElementById(SCROLLER_ID);
    if (el) el.scrollTop = parseInt(saved);
    sessionStorage.removeItem(key);
  }, [key, ready]);
}
