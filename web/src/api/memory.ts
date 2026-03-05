/**
 * Memory API client.
 * Handles fetching facts, approving, updating, and deleting.
 */

import { apiClient } from "./client";
import type { Fact } from "../store/memory";

interface FactsResponse {
  facts: Fact[];
}

export async function fetchFacts(): Promise<Fact[]> {
  const res = await apiClient.get<FactsResponse>("/memory/facts");
  return res.data.facts;
}

export async function approveFact(
  factId: string,
  updatedContent?: string,
): Promise<Fact> {
  const body: Record<string, unknown> = { status: "approved" };
  if (updatedContent !== undefined) {
    body.fact = updatedContent;
  }
  const res = await apiClient.post<Fact>(
    `/memory/facts/${factId}/approve`,
    body,
  );
  return res.data;
}

export async function updateFact(
  factId: string,
  updates: { fact?: string; status?: string },
): Promise<Fact> {
  const res = await apiClient.post<Fact>(
    `/memory/facts/${factId}/update`,
    updates,
  );
  return res.data;
}

export async function deleteFact(factId: string): Promise<void> {
  await apiClient.post(`/memory/facts/${factId}/delete`);
}
