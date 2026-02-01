export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const APP_NAME = 'ReciclaTrac';
export const APP_VERSION = '0.1.0';

export const ROUTES = {
  HOME: '/',
  DASHBOARD: '/',
  LOGIN: '/login',
  PURCHASES: '/purchases',
  SALES: '/sales',
  INVENTORY: '/inventory',
  TREASURY: '/treasury',
  REPORTS: '/reports',
  SETTINGS: '/settings',
} as const;
