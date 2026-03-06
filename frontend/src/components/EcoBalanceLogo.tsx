interface EcoBalanceLogoProps {
  textColor?: "light" | "dark";
  showText?: boolean;
  size?: "sm" | "md" | "lg";
}

function LogoIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 240"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="ecologo-grad1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2bb673" stopOpacity="1" />
          <stop offset="100%" stopColor="#1f8f5f" stopOpacity="1" />
        </linearGradient>
        <linearGradient id="ecologo-grad2" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3ecf8e" stopOpacity="1" />
          <stop offset="100%" stopColor="#2bb673" stopOpacity="1" />
        </linearGradient>
      </defs>
      {/* Base layer */}
      <polygon points="40,170 100,140 160,170 100,200" fill="#6fd3a7" opacity="0.6" />
      {/* Middle layer */}
      <polygon points="35,150 100,120 165,150 100,180" fill="#39b87c" opacity="0.7" />
      {/* Top layer */}
      <polygon points="30,130 100,100 170,130 100,160" fill="url(#ecologo-grad2)" />
      {/* Leaf */}
      <path d="M100 25 C140 70,130 115,100 125 C70 115,60 70,100 25 Z" fill="url(#ecologo-grad1)" />
      {/* Stem */}
      <polygon points="98,60 102,60 101,125 99,125" fill="#d8f3dc" />
    </svg>
  );
}

const sizeConfig = {
  sm: { icon: "h-9", iconWithText: "h-10", title: "text-[17px]", subtitle: "text-[10px]", gap: "gap-2.5", layout: "flex-row items-center" },
  md: { icon: "h-9", iconWithText: "h-10", title: "text-[17px]", subtitle: "text-[10px]", gap: "gap-2.5", layout: "flex-row items-center" },
  lg: { icon: "h-24", iconWithText: "h-24", title: "text-3xl", subtitle: "text-sm", gap: "gap-0", layout: "flex-col items-center" },
};

export default function EcoBalanceLogo({
  textColor = "dark",
  showText = true,
  size = "md",
}: EcoBalanceLogoProps) {
  const cfg = sizeConfig[size];

  if (!showText) {
    return <LogoIcon className={`${cfg.icon} w-auto shrink-0`} />;
  }

  const titleColor = textColor === "light" ? "text-slate-100" : "text-slate-900";
  const subtitleColor = textColor === "light" ? "text-slate-400" : "text-slate-500";

  return (
    <div className={`flex ${cfg.layout} ${cfg.gap}`}>
      <LogoIcon className={`${cfg.iconWithText} w-auto shrink-0`} />
      <div className={`flex flex-col leading-none ${size === "lg" ? "items-center" : ""}`}>
        <span className={`${cfg.title} font-bold tracking-tight ${titleColor}`}>
          EcoBalance
        </span>
        <span className={`${cfg.subtitle} font-semibold uppercase tracking-[0.15em] ${subtitleColor}`}>
          ERP Reciclaje
        </span>
      </div>
    </div>
  );
}
