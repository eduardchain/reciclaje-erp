import { useAuthStore } from "@/stores/authStore";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Building2 } from "lucide-react";
import { APP_NAME } from "@/utils/constants";

export function OrganizationSelector() {
  const navigate = useNavigate();
  const { organizations, setOrganization } = useAuthStore();

  const handleSelect = (orgId: string) => {
    setOrganization(orgId);
    navigate("/");
  };

  return (
    <div className="h-screen flex items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{APP_NAME}</CardTitle>
          <CardDescription>Selecciona una organizacion para continuar</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {organizations.map((org) => (
            <Button
              key={org.id}
              variant="outline"
              className="w-full justify-start h-auto py-3 px-4"
              onClick={() => handleSelect(org.id)}
            >
              <Building2 className="mr-3 h-5 w-5 text-emerald-600" />
              <div className="text-left">
                <div className="font-medium">{org.name}</div>
                {org.member_role && (
                  <div className="text-xs text-muted-foreground capitalize">{org.member_role}</div>
                )}
              </div>
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
