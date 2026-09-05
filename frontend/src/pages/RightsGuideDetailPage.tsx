import { Link, useParams, useSearchParams } from "react-router-dom"
import { ArrowLeft, ExternalLink, Phone, BookOpen } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { useRightsCard } from "@/hooks/useRights"
import { iconFor } from "@/lib/icons"
import type { TargetLanguage } from "@/types"


const SUPPORTED: readonly TargetLanguage[] = ["en", "hi", "bn", "ta", "te", "kn", "mr"]

function coerceLang(v: string | null): TargetLanguage {
  return (v && (SUPPORTED as readonly string[]).includes(v)) ? (v as TargetLanguage) : "en"
}


export function RightsGuideDetailPage() {
  const { topicKey } = useParams<{ topicKey: string }>()
  const [searchParams] = useSearchParams()
  const requestedLang = coerceLang(searchParams.get("lang"))
  const { data: card, isLoading, isError } = useRightsCard(topicKey, requestedLang)

  const Icon = iconFor(card?.icon ?? undefined)

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 md:py-10">

      {/* Back link */}
      <div>
        <Link
          to="/rights"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition"
        >
          <ArrowLeft className="size-4" />
          All rights cards
        </Link>
      </div>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}
      {isError && (
        <p className="text-sm text-red-600 dark:text-red-400">
          Could not load this card. It may not be published yet, or
          there was a network issue.
        </p>
      )}

      {card && (
        <article className="flex flex-col gap-6">

          {/* Title block */}
          <header className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="grid size-10 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
                <Icon className="size-5" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight leading-tight">
                {card.title}
              </h1>
            </div>
            {card.language_fallback && (
              <p className="text-[13px] text-muted-foreground">
                Translation review for your language is in progress.
                Showing the English canonical for now.
              </p>
            )}
          </header>

          {/* Summary */}
          <section aria-label="Summary" className="flex flex-col gap-3 text-[15px] leading-relaxed text-foreground/90">
            {card.summary.split("\n\n").map((para, i) => (
              <p key={i} className="whitespace-pre-line">
                {para}
              </p>
            ))}
          </section>

          {/* Action steps */}
          {card.action_steps.length > 0 && (
            <section aria-label="What to do about it" className="flex flex-col gap-3">
              <div className="text-[11px] font-semibold uppercase tracking-widest text-brand-700 dark:text-brand-200">
                What to do about it
              </div>
              <ol className="flex flex-col gap-3">
                {card.action_steps.map((step, i) => (
                  <li key={i}>
                    <Card>
                      <CardContent className="py-4">
                        <div className="flex items-baseline gap-3">
                          <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-100 text-[13px] font-semibold text-brand-700 dark:bg-brand-900/60 dark:text-brand-100">
                            {i + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            {step.url ? (
                              <a
                                href={step.url}
                                target={step.url.startsWith("http") ? "_blank" : undefined}
                                rel={step.url.startsWith("http") ? "noopener noreferrer" : undefined}
                                className="inline-flex items-baseline gap-1 font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-200 dark:hover:text-brand-100 underline underline-offset-2"
                              >
                                {step.label}
                                {step.url.startsWith("http") && (
                                  <ExternalLink className="size-3.5 self-center" />
                                )}
                              </a>
                            ) : (
                              <span className="font-semibold">{step.label}</span>
                            )}
                            <p className="mt-1 text-[14px] leading-relaxed text-neutral-700 dark:text-neutral-300">
                              {step.description}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* Citation */}
          {card.citation && (
            <section aria-label="Citation" className="rounded-xl border border-neutral-200 bg-neutral-50/60 dark:border-neutral-800 dark:bg-neutral-900/40 px-4 py-4">
              <div className="flex items-start gap-3">
                <BookOpen className="mt-0.5 size-4 shrink-0 text-neutral-500 dark:text-neutral-400" />
                <div className="flex-1">
                  <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
                    Source
                  </div>
                  <div className="text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-line">
                    {card.citation}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* India Labourline callout */}
          <aside className="rounded-xl border border-brand-200 dark:border-brand-900/60 bg-brand-50/50 dark:bg-brand-900/15 px-4 py-4 flex items-start gap-3">
            <Phone className="mt-0.5 size-4 shrink-0 text-brand-700 dark:text-brand-300" />
            <div className="text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
              <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                India Labourline · 1800-419-1550
              </span>
              <br />
              National helpline for labour issues. Free to call. Guides
              you on the right escalation route for your specific
              complaint.
            </div>
          </aside>

          {/* Not-legal-advice disclaimer — Rule 7. Rendered on every
              detail page, styled so a screen reader announces it. */}
          <aside
            role="note"
            aria-label="Not legal advice"
            className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/20 px-4 py-3 text-[13px] leading-relaxed text-amber-900 dark:text-amber-100"
          >
            <span className="font-semibold">Not legal advice.</span>{" "}
            This page shares publicly documented information about your
            rights under Indian law. It is not a substitute for
            professional legal advice. For formal help, call India
            Labourline at{" "}
            <a href="tel:1800-419-1550" className="underline underline-offset-2 font-semibold">
              1800-419-1550
            </a>
            .
          </aside>

        </article>
      )}

    </div>
  )
}
