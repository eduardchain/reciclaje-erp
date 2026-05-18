import { useSearchParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useDateFilter } from "@/stores/dateFilterStore";
import ReportsLayout from "./ReportsLayout";
import ProfitAndLossPeriodView from "./ProfitAndLossPeriodView";
import ProfitAndLossMonthlyView from "./ProfitAndLossMonthlyView";

const VALID_VIEWS = ["period", "monthly"] as const;
type PnlView = (typeof VALID_VIEWS)[number];

export default function ProfitAndLossPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { pnlView, setPnlView } = useDateFilter();
  const rawView = searchParams.get("view");
  // Source of truth: URL > store > "period". Persistir en store al cambiar para
  // que al volver desde sidebar (sin params) se restaure el ultimo tab usado.
  const validUrlView = (VALID_VIEWS as readonly string[]).includes(rawView ?? "")
    ? (rawView as PnlView)
    : null;
  const view: PnlView = validUrlView ?? pnlView;

  const setView = (v: string) => {
    const next: PnlView = (VALID_VIEWS as readonly string[]).includes(v) ? (v as PnlView) : "period";
    setPnlView(next);
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      if (next === "period") params.delete("view");
      else params.set("view", next);
      return params;
    }, { replace: true });
  };

  return (
    <ReportsLayout>
      <Tabs value={view} onValueChange={setView} className="space-y-4">
        <TabsList>
          <TabsTrigger value="period">Periodo</TabsTrigger>
          <TabsTrigger value="monthly">Mensual</TabsTrigger>
        </TabsList>
        <TabsContent value="period" className="space-y-4">
          <ProfitAndLossPeriodView />
        </TabsContent>
        <TabsContent value="monthly" className="space-y-4">
          <ProfitAndLossMonthlyView />
        </TabsContent>
      </Tabs>
    </ReportsLayout>
  );
}
