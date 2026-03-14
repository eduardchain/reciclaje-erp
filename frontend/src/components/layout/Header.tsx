import { useState } from "react";
import { Building2, KeyRound, LogOut, User } from "lucide-react";
import EcoBalanceLogo from "@/components/EcoBalanceLogo";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogout, useCurrentUser, useCurrentOrganization, useChangePassword } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/utils/formatters";

export default function Header() {
  const user = useCurrentUser();
  const org = useCurrentOrganization();
  const logout = useLogout();
  const changePassword = useChangePassword();

  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "U";

  const passwordsMatch = newPassword === confirmPassword;
  const newPasswordValid = newPassword.length >= 6;
  const canSubmit = currentPassword && newPassword && confirmPassword && passwordsMatch && newPasswordValid;

  const handleChangePassword = () => {
    if (!canSubmit) return;
    setPasswordError("");
    changePassword.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setShowChangePassword(false);
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
          setPasswordError("");
        },
        onError: (error: unknown) => {
          setPasswordError(getApiErrorMessage(error, "Error al cambiar contraseña"));
        },
      },
    );
  };

  return (
    <>
      <header className="bg-white border-b border-slate-200/80 h-16 flex items-center px-6">
        <div className="flex items-center justify-between w-full">
          <EcoBalanceLogo textColor="dark" />

          <div className="flex items-center gap-4">
            {org && (
              <div className="flex items-center gap-1.5 text-sm text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg">
                <Building2 className="w-3.5 h-3.5" />
                <span className="font-medium">{org.name}</span>
              </div>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2.5 focus:outline-none hover:opacity-80 transition-opacity">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-emerald-100 text-emerald-700 text-xs font-semibold">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  {user && (
                    <div className="hidden sm:block text-left">
                      <p className="text-sm font-medium text-slate-700 leading-tight">
                        {user.full_name}
                      </p>
                      <p className="text-[11px] text-slate-400 leading-tight">
                        {user.email}
                      </p>
                    </div>
                  )}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem disabled>
                  <User className="mr-2 h-4 w-4" />
                  Mi perfil
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShowChangePassword(true)}>
                  <KeyRound className="mr-2 h-4 w-4" />
                  Cambiar Contraseña
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="text-red-600 focus:text-red-600">
                  <LogOut className="mr-2 h-4 w-4" />
                  Cerrar sesion
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <Dialog open={showChangePassword} onOpenChange={setShowChangePassword}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Cambiar Contraseña</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Contraseña actual</Label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => { setCurrentPassword(e.target.value); setPasswordError(""); }}
                placeholder="Ingresa tu contraseña actual"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nueva contraseña</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimo 6 caracteres"
                className="mt-1"
              />
              {newPassword && !newPasswordValid && (
                <p className="text-xs text-red-500 mt-1">Minimo 6 caracteres</p>
              )}
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Confirmar contraseña</Label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repite la nueva contraseña"
                className="mt-1"
              />
              {confirmPassword && !passwordsMatch && (
                <p className="text-xs text-red-500 mt-1">Las contraseñas no coinciden</p>
              )}
            </div>
            {passwordError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{passwordError}</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowChangePassword(false)}>Cancelar</Button>
            <Button
              onClick={handleChangePassword}
              disabled={!canSubmit || changePassword.isPending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {changePassword.isPending ? "Cambiando..." : "Cambiar Contraseña"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
