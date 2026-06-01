import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Header from "./Header";
import Sidebar from "./Sidebar";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/useMediaQuery";

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[50vh]">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-emerald-600" />
    </div>
  );
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMobile = useIsMobile();
  const location = useLocation();

  // Cerrar drawer al cambiar de ruta (auto-close on nav)
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Cerrar drawer si se cruza el breakpoint hacia desktop
  useEffect(() => {
    if (!isMobile && mobileOpen) setMobileOpen(false);
  }, [isMobile, mobileOpen]);

  return (
    <div className="h-screen flex overflow-hidden">
      {/* Sidebar desktop: oculto bajo md */}
      <div className="hidden md:flex">
        <Sidebar mode="desktop" />
      </div>

      {/* Sidebar mobile: drawer via shadcn Sheet */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 w-72 max-w-[85vw] bg-sidebar-bg border-r-0">
          <Sidebar mode="mobile" onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex-1 flex flex-col min-w-0">
        <Header onMenuClick={() => setMobileOpen(true)} />
        <main id="main-scroll" className="flex-1 overflow-y-auto bg-slate-50/80">
          <div className="container mx-auto p-3 md:p-6 animate-fade-in">
            <Suspense fallback={<PageLoader />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}
