import { create } from "zustand";
import { persist } from "zustand/middleware";

function getDefaultDates() {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  return {
    dateFrom: firstDay.toISOString().slice(0, 10),
    dateTo: now.toISOString().slice(0, 10),
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
