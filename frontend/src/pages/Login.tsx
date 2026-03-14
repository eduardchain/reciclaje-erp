import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";
import { getApiErrorMessage } from "@/utils/formatters";
import EcoBalanceLogo from "@/components/EcoBalanceLogo";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const login = useLogin();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    login.mutate(
      { email, password },
      {
        onError: (error: unknown) => {
          setLoginError(getApiErrorMessage(error, "Correo o contraseña incorrectos"));
        },
      },
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="flex flex-col items-center">
          <EcoBalanceLogo textColor="dark" size="lg" />
          <p className="mt-4 text-center text-sm text-slate-600">
            Iniciar sesion en el sistema
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Correo electronico</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setLoginError(""); }}
                placeholder="correo@ejemplo.com"
              />
            </div>
            <div>
              <Label htmlFor="password">Contrasena</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => { setPassword(e.target.value); setLoginError(""); }}
                placeholder="Tu contrasena"
              />
            </div>
          </div>

          {loginError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{loginError}</p>
          )}

          <Button
            type="submit"
            className="w-full bg-emerald-600 hover:bg-emerald-700"
            disabled={login.isPending}
          >
            {login.isPending ? "Ingresando..." : "Iniciar sesion"}
          </Button>
        </form>

        <div className="text-center">
          <p className="text-xs text-slate-500">
            &copy; 2026 Eduardo Chain. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </div>
  );
}
