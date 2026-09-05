import { useMutation, useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type {
  MatchResponse,
  SchemeDetail,
  SchemesListResponse,
  TargetLanguage,
  WorkerProfile,
} from "@/types"


export const schemeKeys = {
  all: ["schemes"] as const,
  list: (language: TargetLanguage) =>
    [...schemeKeys.all, "list", language] as const,
  detail: (key: string, language: TargetLanguage) =>
    [...schemeKeys.all, "detail", key, language] as const,
}


export function useSchemesList(language: TargetLanguage) {
  return useQuery({
    queryKey: schemeKeys.list(language),
    queryFn: async (): Promise<SchemesListResponse> => {
      const { data } = await api.get<SchemesListResponse>("/api/schemes", {
        params: { language },
      })
      return data
    },
    staleTime: 5 * 60_000,
  })
}


export function useSchemeDetail(key: string | undefined, language: TargetLanguage) {
  return useQuery({
    queryKey: key ? schemeKeys.detail(key, language) : ["scheme-detail-noop"],
    queryFn: async (): Promise<SchemeDetail> => {
      const { data } = await api.get<SchemeDetail>(`/api/schemes/${key}`, {
        params: { language },
      })
      return data
    },
    enabled: !!key,
    staleTime: 5 * 60_000,
  })
}


/**
 * Fire the /api/schemes/match POST when the worker submits the
 * wizard. Kept as a mutation (not a query) because the trigger is
 * explicit — no auto-refetch.
 */
export function useMatchSchemes(language: TargetLanguage) {
  return useMutation({
    mutationFn: async (profile: WorkerProfile): Promise<MatchResponse> => {
      const { data } = await api.post<MatchResponse>(
        "/api/schemes/match",
        profile,
        { params: { language } },
      )
      return data
    },
  })
}
