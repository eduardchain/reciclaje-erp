import { Input } from "@/components/ui/input";
import { Calendar } from "lucide-react";

interface DateRangePickerProps {
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (date: string) => void;
  onDateToChange: (date: string) => void;
}

export function DateRangePicker({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: DateRangePickerProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full sm:w-auto">
      <div className="flex items-center gap-2 w-full sm:w-auto">
        <Calendar className="h-4 w-4 text-slate-400 shrink-0" />
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          className="w-full sm:w-40"
        />
      </div>
      <span className="hidden sm:inline text-slate-400">-</span>
      <Input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        className="w-full sm:w-40"
      />
    </div>
  );
}
