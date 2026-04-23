import { Link, useLocation } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { ReactNode } from "react";
import { ROUTES, buildRoute } from "@/utils/constants";

interface EntityLinkProps {
  to: string | null | undefined;
  children: ReactNode;
  showIcon?: boolean;
  iconSize?: number;
  className?: string;
  returnTo?: string;
  title?: string;
}

export function EntityLink({
  to,
  children,
  showIcon = true,
  iconSize = 14,
  className,
  returnTo,
  title,
}: EntityLinkProps) {
  const location = useLocation();

  if (!to) {
    return <span>{children}</span>;
  }

  const currentPath = location.pathname + location.search;
  const encodedReturn = encodeURIComponent(returnTo ?? currentPath);
  const separator = to.includes("?") ? "&" : "?";
  const finalTo = `${to}${separator}returnTo=${encodedReturn}`;

  const defaultClass =
    "text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-1 cursor-pointer";

  return (
    <Link
      to={finalTo}
      className={className ?? defaultClass}
      title={title}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
      {showIcon && <ExternalLink size={iconSize} />}
    </Link>
  );
}

// Wrappers tipados

interface IdProps {
  id: string | null | undefined;
  children: ReactNode;
  showIcon?: boolean;
  className?: string;
}

export function ThirdPartyLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? `${ROUTES.TREASURY_ACCOUNT_STATEMENT}?third_party_id=${id}` : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function PurchaseLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.PURCHASE_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function SaleLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.SALE_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function DoubleEntryLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.DOUBLE_ENTRY_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function TransformationLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.INVENTORY_TRANSFORMATION_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function AdjustmentLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.INVENTORY_ADJUSTMENT_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function MoneyMovementLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? buildRoute(ROUTES.TREASURY_MOVEMENT_DETAIL, { id }) : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}

export function AccountLink({ id, children, showIcon, className }: IdProps) {
  const to = id ? `${ROUTES.TREASURY_ACCOUNT_MOVEMENTS}?account_id=${id}` : null;
  return (
    <EntityLink to={to} showIcon={showIcon} className={className}>
      {children}
    </EntityLink>
  );
}
