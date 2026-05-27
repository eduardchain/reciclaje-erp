interface ResponsiveFilterBarProps {
  children: React.ReactNode;
  className?: string;
}

export function ResponsiveFilterBar({ children, className }: ResponsiveFilterBarProps) {
  return (
    <div className={`flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center ${className ?? ""}`}>
      {children}
    </div>
  );
}
