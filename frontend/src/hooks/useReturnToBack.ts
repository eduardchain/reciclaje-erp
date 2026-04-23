import { useNavigate, useLocation } from "react-router-dom";

export function useReturnToBack(fallbackRoute?: string) {
  const navigate = useNavigate();
  const location = useLocation();

  return () => {
    const rt = new URLSearchParams(location.search).get("returnTo");
    if (rt) {
      navigate(rt);
    } else if (fallbackRoute) {
      navigate(fallbackRoute);
    } else {
      navigate(-1);
    }
  };
}
