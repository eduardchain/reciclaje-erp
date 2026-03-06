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
}

const defaults = getDefaultDates();

export const useDateFilter = create<DateFilterStore>()(
  persist(
    (set) => ({
      dateFrom: defaults.dateFrom,
      dateTo: defaults.dateTo,
      setDateFrom: (d) => set({ dateFrom: d }),
      setDateTo: (d) => set({ dateTo: d }),
    }),
    { name: "date-filter" },
  ),
);
