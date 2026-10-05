"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AnalyticsOverview, DashboardData } from "@/lib/types";
import { qk } from "./rooms";

export function useDashboard() {
  return useQuery({ queryKey: qk.dashboard, queryFn: () => api<DashboardData>("/dashboard"), refetchInterval: 20_000 });
}

export function useAnalyticsOverview() {
  return useQuery({ queryKey: qk.overview, queryFn: () => api<AnalyticsOverview>("/analytics/overview") });
}
