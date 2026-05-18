import { create } from "zustand";
import { persist } from "zustand/middleware";
import { toLocalDateInput } from "@/utils/formatters";

function getDefaultDates() {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  return {
    dateFrom: toLocalDateInput(firstDay),
    dateTo: toLocalDateInput(now),
  };
}

interface DateFilterStore {
  dateFrom: string;
  dateTo: string;
  setDateFrom: (d: string) => void;
  setDateTo: (d: string) => void;
  balanceAsOfDate: string;
  setBalanceAsOfDate: (d: string) => void;
  pnlView: "period" | "monthly";
  setPnlView: (v: "period" | "monthly") => void;
  pnlCutoffDay: number;
  setPnlCutoffDay: (d: number) => void;
}

const defaults = getDefaultDates();

export const useDateFilter = create<DateFilterStore>()(
  persist(
    (set) => ({
      dateFrom: defaults.dateFrom,
      dateTo: defaults.dateTo,
      setDateFrom: (d) => set({ dateFrom: d }),
      setDateTo: (d) => set({ dateTo: d }),
      balanceAsOfDate: "",
      setBalanceAsOfDate: (d) => set({ balanceAsOfDate: d }),
      pnlView: "period",
      setPnlView: (v) => set({ pnlView: v }),
      pnlCutoffDay: 1,
      setPnlCutoffDay: (d) => set({ pnlCutoffDay: d }),
    }),
    { name: "date-filter" },
  ),
);
