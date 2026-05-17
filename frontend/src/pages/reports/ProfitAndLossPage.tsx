import { useSearchParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ReportsLayout from "./ReportsLayout";
import ProfitAndLossPeriodView from "./ProfitAndLossPeriodView";
import ProfitAndLossMonthlyView from "./ProfitAndLossMonthlyView";

const VALID_VIEWS = ["period", "monthly"] as const;
type PnlView = (typeof VALID_VIEWS)[number];

export default function ProfitAndLossPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawView = searchParams.get("view");
  // Fallback silencioso a "period" si valor invalido (decision #50).
  const view: PnlView = (VALID_VIEWS as readonly string[]).includes(rawView ?? "")
    ? (rawView as PnlView)
    : "period";

  const setView = (v: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "period") next.delete("view");
      else next.set("view", v);
      return next;
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
