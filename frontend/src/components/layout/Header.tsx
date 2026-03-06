import { Building2, LogOut, User } from "lucide-react";
import EcoBalanceLogo from "@/components/EcoBalanceLogo";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useLogout, useCurrentUser, useCurrentOrganization } from "@/hooks/useAuth";

export default function Header() {
  const user = useCurrentUser();
  const org = useCurrentOrganization();
  const logout = useLogout();

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "U";

  return (
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
  );
}
