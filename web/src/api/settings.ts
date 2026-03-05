/**
 * Settings API client — fetches and updates settings and usage data.
 */

import { apiClient } from "./client";
import type { Settings, UsageData } from "../store/settings";

export async function fetchSettings(): Promise<Settings> {
  const res = await apiClient.get<Settings>("/settings");
  return res.data;
}

export async function updateSettings(
  settings: Partial<Settings>,
): Promise<Settings> {
  const res = await apiClient.post<Settings>("/settings", settings);
  return res.data;
}

export async function fetchUsage(): Promise<UsageData> {
  const res = await apiClient.get<UsageData>("/usage");
  return res.data;
}
