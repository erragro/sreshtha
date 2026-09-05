import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, Phone, ShieldCheck } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { useRightsCards } from "@/hooks/useRights"
import { iconFor } from "@/lib/icons"
import { cn } from "@/lib/utils"
import type { TargetLanguage } from "@/types"


// Order mirrors ContractReaderPage: Hindi first (broadest reach for
// Indian gig workers), then Bengali, Tamil, other Indic, English last.
// English still ships as the canonical every time; the switcher lets a
// worker pick a language once translation review lands.
const LANGUAGE_OPTIONS: { code: TargetLanguage; label: string; nativeLabel: string }[] = [
  { code: "hi", label: "Hindi",   nativeLabel: "हिन्दी" },
  { code: "bn", label: "Bengali", nativeLabel: "বাংলা" },
  { code: "ta", label: "Tamil",   nativeLabel: "தமிழ்" },
  { code: "te", label: "Telugu",  nativeLabel: "తెలుగు" },
  { code: "kn", label: "Kannada", nativeLabel: "ಕನ್ನಡ" },
  { code: "mr", label: "Marathi", nativeLabel: "मराठी" },
  { code: "en", label: "English", nativeLabel: "English" },
]


export function RightsGuidePage() {
  const [requestedLang, setRequestedLang] = useState<TargetLanguage>("en")
  const { data, isLoading, isError } = useRightsCards(requestedLang)

  const actualLang = data?.language ?? requestedLang
  const fallback = actualLang !== requestedLang
  const cards = data?.cards ?? []

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 md:py-10">

      {/* Header */}
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
            <ShieldCheck className="size-5" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Rights Guide</h1>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Plain-language summaries of laws and government schemes that
          apply to Indian gig workers, with citations to the source.
        </p>
      </header>

      {/* Persistent disclaimer strip — Rule 7 in the content guidelines. */}
      <aside
        role="note"
        aria-label="Not legal advice"
        className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/20 px-4 py-3 text-[13px] leading-relaxed text-amber-900 dark:text-amber-100"
      >
        <span className="font-semibold">Not legal advice.</span>{" "}
        Rights Guide shares publicly documented information. For formal
        help, call India Labourline at{" "}
        <a href="tel:1800-419-1550" className="underline underline-offset-2 font-semibold">
          1800-419-1550
        </a>
        .
      </aside>

      {/* Language switcher */}
      <section aria-label="Language" className="flex flex-col gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Read in
        </div>
        <div className="flex flex-wrap gap-2">
          {LANGUAGE_OPTIONS.map((opt) => (
            <button
              key={opt.code}
              type="button"
              onClick={() => setRequestedLang(opt.code)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition",
                requestedLang === opt.code
                  ? "border-brand-500 bg-brand-50 text-brand-800 dark:border-brand-400 dark:bg-brand-900/40 dark:text-brand-100"
                  : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900/40 dark:text-neutral-300",
              )}
            >
              <span className="font-medium">{opt.nativeLabel}</span>
              {opt.nativeLabel !== opt.label && (
                <span className="ml-1.5 text-[11px] text-muted-foreground">{opt.label}</span>
              )}
            </button>
          ))}
        </div>

        {fallback && (
          <p className="text-[13px] text-muted-foreground">
            Translation review for this language is in progress. Showing
            the English canonical for now.
          </p>
        )}
      </section>

      {/* Cards */}
      <section aria-label="Fact cards" className="flex flex-col gap-3">
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {isError && (
          <p className="text-sm text-red-600 dark:text-red-400">
            Could not load Rights Guide. Try again in a moment.
          </p>
        )}
        {!isLoading && cards.length === 0 && !isError && (
          <p className="text-sm text-muted-foreground">
            No cards yet. Content is being written and reviewed.
          </p>
        )}

        {cards.map((c) => {
          const Icon = iconFor(c.icon ?? undefined)
          return (
            <Link
              key={c.topic_key}
              to={`/rights/${c.topic_key}?lang=${actualLang}`}
              className="group"
            >
              <Card className="transition group-hover:border-brand-300 dark:group-hover:border-brand-700">
                <CardContent className="flex items-center gap-3 py-4">
                  <div className="grid size-9 place-items-center rounded-lg bg-neutral-100 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                    <Icon className="size-4" />
                  </div>
                  <div className="flex-1">
                    <div className="text-[15px] font-semibold leading-tight">
                      {c.title}
                    </div>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground transition group-hover:translate-x-0.5" />
                </CardContent>
              </Card>
            </Link>
          )
        })}
      </section>

      {/* Labourline callout at the tail of the list. */}
      <aside className="mt-4 rounded-xl border border-brand-200 dark:border-brand-900/60 bg-brand-50/50 dark:bg-brand-900/15 px-4 py-4 flex items-start gap-3">
        <Phone className="mt-0.5 size-4 shrink-0 text-brand-700 dark:text-brand-300" />
        <div className="text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
          <span className="font-semibold text-neutral-900 dark:text-neutral-100">
            India Labourline · 1800-419-1550
          </span>
          <br />
          National helpline operated by the Ministry of Labour and
          Employment. Free to call. They guide you to the right
          authority for your specific complaint.
        </div>
      </aside>

    </div>
  )
}
