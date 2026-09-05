import { Link, useParams, useSearchParams } from "react-router-dom"
import { ArrowLeft, ExternalLink, FileText, Landmark, Phone, Timer } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { useSchemeDetail } from "@/hooks/useSchemes"
import { iconFor } from "@/lib/icons"
import type { TargetLanguage } from "@/types"


const SUPPORTED: readonly TargetLanguage[] = ["en", "hi", "bn", "ta", "te", "kn", "mr"]
function coerceLang(v: string | null): TargetLanguage {
  return (v && (SUPPORTED as readonly string[]).includes(v)) ? (v as TargetLanguage) : "en"
}


export function SchemeDetailPage() {
  const { key } = useParams<{ key: string }>()
  const [searchParams] = useSearchParams()
  const requestedLang = coerceLang(searchParams.get("lang"))
  const { data: s, isLoading, isError } = useSchemeDetail(key, requestedLang)

  const Icon = iconFor(s?.icon ?? undefined)

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 md:py-10">

      <div>
        <Link
          to="/schemes"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition"
        >
          <ArrowLeft className="size-4" />
          Back to Schemes Finder
        </Link>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {isError && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Could not load this scheme. It may not be published yet.
        </p>
      )}

      {s && (
        <article className="flex flex-col gap-6">

          <header className="flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
                <Icon className="size-5" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight leading-tight">
                {s.name}
              </h1>
            </div>
            <div className="flex flex-wrap gap-2 text-[12px] text-muted-foreground">
              {s.state_scope && (
                <span className="rounded-full bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5">
                  {s.state_scope === "all" ? "All India" : s.state_scope}
                </span>
              )}
              {s.estimated_time && (
                <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5">
                  <Timer className="size-3" />
                  {s.estimated_time}
                </span>
              )}
            </div>
            {s.language_fallback && (
              <p className="text-[13px] text-muted-foreground">
                Translation review for your language is in progress.
                Showing the English canonical for now.
              </p>
            )}
          </header>

          {/* Description */}
          <section aria-label="Description" className="flex flex-col gap-3 text-[15px] leading-relaxed text-foreground/90">
            {s.description.split("\n\n").map((para, i) => (
              <p key={i} className="whitespace-pre-line">{para}</p>
            ))}
          </section>

          {/* Documents needed */}
          {s.docs_needed.length > 0 && (
            <section aria-label="Documents needed" className="flex flex-col gap-3">
              <div className="text-[11px] font-semibold uppercase tracking-widest text-brand-700 dark:text-brand-200">
                Documents you'll need
              </div>
              <ul className="flex flex-col gap-2">
                {s.docs_needed.map((d, i) => (
                  <li key={i}>
                    <Card>
                      <CardContent className="flex items-start gap-3 py-3">
                        <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                        <div className="flex-1">
                          <div className="text-sm font-medium">{d.name}</div>
                          {d.note && (
                            <div className="mt-0.5 text-[12px] text-muted-foreground">
                              {d.note}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Apply CTA */}
          {s.apply_url && (
            <section aria-label="Apply">
              {s.apply_note && (
                <p className="mb-3 text-[14px] leading-relaxed text-neutral-700 dark:text-neutral-300">
                  {s.apply_note}
                </p>
              )}
              <a
                href={s.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700"
              >
                Apply on the official portal
                <ExternalLink className="size-4" />
              </a>
              <p className="mt-2 text-[12px] text-muted-foreground">
                Opens {new URL(s.apply_url).host} in a new tab.
              </p>
            </section>
          )}

          {/* Labourline callout */}
          <aside className="rounded-xl border border-brand-200 dark:border-brand-900/60 bg-brand-50/50 dark:bg-brand-900/15 px-4 py-4 flex items-start gap-3">
            <Phone className="mt-0.5 size-4 shrink-0 text-brand-700 dark:text-brand-300" />
            <div className="text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
              <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                India Labourline · 1800-419-1550
              </span>
              <br />
              For help finding the right office or understanding the
              paperwork. Free to call.
            </div>
          </aside>

          {/* Disclaimer */}
          <aside
            role="note"
            className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/20 px-4 py-3 text-[13px] leading-relaxed text-amber-900 dark:text-amber-100"
          >
            <span className="font-semibold">Not a guarantee of eligibility.</span>{" "}
            Sreshtha describes what the scheme is intended for; the
            official portal decides who qualifies. Benefit amounts and
            deadlines may have changed since this page was written —
            trust the portal for current figures.
          </aside>

        </article>
      )}

    </div>
  )
}
