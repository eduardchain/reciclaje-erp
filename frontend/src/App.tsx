import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from '@/components/layout/Layout';
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';
import NotFound from '@/pages/NotFound';
import { ROUTES } from '@/utils/constants';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path={ROUTES.LOGIN} element={<Login />} />
          
          {/* Protected routes with layout */}
          <Route element={<Layout />}>
            <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
            <Route path={ROUTES.PURCHASES} element={<div>Compras (Coming soon)</div>} />
            <Route path={ROUTES.SALES} element={<div>Ventas (Coming soon)</div>} />
            <Route path={ROUTES.INVENTORY} element={<div>Inventario (Coming soon)</div>} />
            <Route path={ROUTES.TREASURY} element={<div>Tesorería (Coming soon)</div>} />
            <Route path={ROUTES.REPORTS} element={<div>Reportes (Coming soon)</div>} />
          </Route>

          {/* 404 route */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
