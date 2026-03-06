import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useCreateThirdParty, useUpdateThirdParty } from "@/hooks/useCrudData";
import type { ThirdPartyResponse } from "@/types/third-party";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editItem: ThirdPartyResponse | null;
}

export default function ThirdPartyFormDialog({ open, onOpenChange, editItem }: Props) {
  const create = useCreateThirdParty();
  const update = useUpdateThirdParty();

  const [name, setName] = useState("");
  const [identification, setIdentification] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [isSupplier, setIsSupplier] = useState(false);
  const [isCustomer, setIsCustomer] = useState(false);
  const [isInvestor, setIsInvestor] = useState(false);
  const [isProvision, setIsProvision] = useState(false);

  useEffect(() => {
    if (editItem) {
      setName(editItem.name);
      setIdentification(editItem.identification_number ?? "");
      setEmail(editItem.email ?? "");
      setPhone(editItem.phone ?? "");
      setAddress(editItem.address ?? "");
      setIsSupplier(editItem.is_supplier);
      setIsCustomer(editItem.is_customer);
      setIsInvestor(editItem.is_investor);
      setIsProvision(editItem.is_provision);
    } else {
      setName(""); setIdentification(""); setEmail(""); setPhone(""); setAddress("");
      setIsSupplier(false); setIsCustomer(false); setIsInvestor(false); setIsProvision(false);
    }
  }, [editItem, open]);

  const handleSubmit = () => {
    const data = {
      name,
      identification_number: identification || null,
      email: email || null,
      phone: phone || null,
      address: address || null,
      is_supplier: isSupplier,
      is_customer: isCustomer,
      is_investor: isInvestor,
      is_provision: isProvision,
    };
    const opts = { onSuccess: () => onOpenChange(false) };

    if (editItem) {
      update.mutate({ id: editItem.id, data }, opts);
    } else {
      create.mutate(data, opts);
    }
  };

  const isPending = create.isPending || update.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{editItem ? "Editar Tercero" : "Nuevo Tercero"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Nombre *</Label><Input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Identificacion</Label><Input value={identification} onChange={(e) => setIdentification(e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Telefono</Label><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
          </div>
          <div><Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Direccion</Label><Input value={address} onChange={(e) => setAddress(e.target.value)} /></div>
          <div className="space-y-3">
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Roles</Label>
            <div className="flex items-center justify-between"><span className="text-sm">Proveedor</span><Switch checked={isSupplier} onCheckedChange={setIsSupplier} /></div>
            <div className="flex items-center justify-between"><span className="text-sm">Cliente</span><Switch checked={isCustomer} onCheckedChange={setIsCustomer} /></div>
            <div className="flex items-center justify-between"><span className="text-sm">Inversionista</span><Switch checked={isInvestor} onCheckedChange={setIsInvestor} /></div>
            <div className="flex items-center justify-between"><span className="text-sm">Provision</span><Switch checked={isProvision} onCheckedChange={setIsProvision} /></div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          <Button onClick={handleSubmit} disabled={!name || isPending} className="bg-emerald-600 hover:bg-emerald-700">
            {isPending ? "Guardando..." : editItem ? "Actualizar" : "Crear"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
