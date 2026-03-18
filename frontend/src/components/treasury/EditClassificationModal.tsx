import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { EntitySelect } from "@/components/shared/EntitySelect";
import { BusinessUnitAllocationSelector } from "@/components/shared/BusinessUnitAllocationSelector";
import { useExpenseCategoriesFlat } from "@/hooks/useMasterData";
import { formatCurrency, formatDate } from "@/utils/formatters";
import type { MoneyMovementResponse, UpdateClassificationRequest } from "@/types/money-movement";

type AllocationType = "direct" | "shared" | "general";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  movement: MoneyMovementResponse;
  onSave: (data: UpdateClassificationRequest) => void;
  loading: boolean;
}

function deriveAllocationType(movement: MoneyMovementResponse): AllocationType {
  if (movement.business_unit_id) return "direct";
  if (movement.applicable_business_unit_ids?.length) return "shared";
  return "general";
}

export function EditClassificationModal({ open, onOpenChange, movement, onSave, loading }: Props) {
  const { data: categoriesData } = useExpenseCategoriesFlat();
  const categories = categoriesData?.items ?? [];

  const [categoryId, setCategoryId] = useState(movement.expense_category_id ?? "");
  const [businessUnitId, setBusinessUnitId] = useState(movement.business_unit_id ?? "");
  const [applicableIds, setApplicableIds] = useState<string[]>(movement.applicable_business_unit_ids ?? []);
  const [allocationType, setAllocationType] = useState<AllocationType>(deriveAllocationType(movement));

  // Reinicializar al abrir con otro movimiento
  useEffect(() => {
    if (open) {
      setCategoryId(movement.expense_category_id ?? "");
      setBusinessUnitId(movement.business_unit_id ?? "");
      setApplicableIds(movement.applicable_business_unit_ids ?? []);
      setAllocationType(deriveAllocationType(movement));
    }
  }, [open, movement]);

  const handleSave = () => {
    const payload: UpdateClassificationRequest = {
      expense_category_id: categoryId,
      business_unit_id: allocationType === "direct" ? businessUnitId || null : null,
      applicable_business_unit_ids: allocationType === "shared" && applicableIds.length > 0 ? applicableIds : null,
    };
    onSave(payload);
  };

  const canSave = !!categoryId && (allocationType !== "direct" || !!businessUnitId) && (allocationType !== "shared" || applicableIds.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Editar Clasificacion</DialogTitle>
        </DialogHeader>

        {/* Seccion read-only */}
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Fecha</dt><dd>{formatDate(movement.date)}</dd></div>
          <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monto</dt><dd className="font-bold">{formatCurrency(movement.amount)}</dd></div>
          {movement.account_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cuenta</dt><dd>{movement.account_name}</dd></div>}
          {movement.third_party_name && <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tercero</dt><dd>{movement.third_party_name}</dd></div>}
          <div className="flex justify-between"><dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">Descripcion</dt><dd>{movement.description}</dd></div>
        </dl>

        <Separator />

        {/* Seccion editable */}
        <div className="space-y-4">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Categoria de Gasto</Label>
            <EntitySelect
              value={categoryId}
              onChange={setCategoryId}
              options={categories.map((c) => ({ id: c.id, label: c.display_name }))}
              placeholder="Seleccionar categoria..."
            />
          </div>

          <BusinessUnitAllocationSelector
            businessUnitId={businessUnitId}
            setBusinessUnitId={setBusinessUnitId}
            applicableBusinessUnitIds={applicableIds}
            setApplicableBusinessUnitIds={setApplicableIds}
            allocationType={allocationType}
            setAllocationType={setAllocationType}
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>Cancelar</Button>
          <Button onClick={handleSave} disabled={!canSave || loading}>{loading ? "Guardando..." : "Guardar"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
