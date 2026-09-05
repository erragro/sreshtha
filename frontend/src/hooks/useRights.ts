import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import type {
  FactCardDetail,
  FactCardListResponse,
  TargetLanguage,
} from "@/types"


export const rightsKeys = {
  all: ["rights"] as const,
  list: (language: TargetLanguage) => [...rightsKeys.all, "list", language] as const,
  detail: (topicKey: string, language: TargetLanguage) =>
    [...rightsKeys.all, "detail", topicKey, language] as const,
}


/**
 * List of active Rights Guide cards for a given language. The API
 * silently falls back to English when the requested language is not
 * yet active — check the returned `language` field against what was
 * requested to decide whether to surface a "translation in review"
 * note.
 */
export function useRightsCards(language: TargetLanguage) {
  return useQuery({
    queryKey: rightsKeys.list(language),
    queryFn: async (): Promise<FactCardListResponse> => {
      const { data } = await api.get<FactCardListResponse>("/api/rights/cards", {
        params: { language },
      })
      return data
    },
    staleTime: 5 * 60_000, // content is migration-authored; 5 min is fine
  })
}


/**
 * Detail view for one topic. Same fallback semantics as the list —
 * `language_fallback` in the response tells the UI whether the copy is
 * in the requested language or the English canonical.
 */
export function useRightsCard(topicKey: string | undefined, language: TargetLanguage) {
  return useQuery({
    queryKey: topicKey
      ? rightsKeys.detail(topicKey, language)
      : ["rights-detail-noop"],
    queryFn: async (): Promise<FactCardDetail> => {
      const { data } = await api.get<FactCardDetail>(
        `/api/rights/cards/${topicKey}`,
        { params: { language } },
      )
      return data
    },
    enabled: !!topicKey,
    staleTime: 5 * 60_000,
  })
}
