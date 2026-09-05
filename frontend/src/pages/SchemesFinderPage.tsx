import { useState } from "react"
import { Link } from "react-router-dom"
import { Award, ChevronRight, Landmark, Loader2, Phone } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { useMatchSchemes, useSchemesList } from "@/hooks/useSchemes"
import { iconFor } from "@/lib/icons"
import { cn } from "@/lib/utils"
import type { TargetLanguage, WorkerProfile } from "@/types"


const LANGUAGE_OPTIONS: { code: TargetLanguage; label: string; nativeLabel: string }[] = [
  { code: "hi", label: "Hindi",   nativeLabel: "हिन्दी" },
  { code: "bn", label: "Bengali", nativeLabel: "বাংলা" },
  { code: "ta", label: "Tamil",   nativeLabel: "தமிழ்" },
  { code: "te", label: "Telugu",  nativeLabel: "తెలుగు" },
  { code: "kn", label: "Kannada", nativeLabel: "ಕನ್ನಡ" },
  { code: "mr", label: "Marathi", nativeLabel: "मराठी" },
  { code: "en", label: "English", nativeLabel: "English" },
]

// Not exhaustive — just the states that actually have gig-worker
// welfare boards or schemes today. The API accepts anything and
// simply won't match state-scoped schemes if a state isn't seeded.
const STATE_OPTIONS: { code: string; label: string }[] = [
  { code: "karnataka",     label: "Karnataka" },
  { code: "rajasthan",     label: "Rajasthan" },
  { code: "tamil_nadu",    label: "Tamil Nadu" },
  { code: "maharashtra",   label: "Maharashtra" },
  { code: "west_bengal",   label: "West Bengal" },
  { code: "delhi",         label: "Delhi" },
  { code: "uttar_pradesh", label: "Uttar Pradesh" },
  { code: "other",         label: "Other" },
]

const OCCUPATION_OPTIONS: { code: string; label: string }[] = [
  { code: "delivery", label: "Delivery" },
  { code: "cab",      label: "Cab / auto driver" },
  { code: "domestic", label: "Domestic work" },
  { code: "trades",   label: "Trades" },
  { code: "any",      label: "Other / mixed" },
]

const GENDER_OPTIONS: { code: string; label: string }[] = [
  { code: "female", label: "Female" },
  { code: "male",   label: "Male" },
  { code: "other",  label: "Prefer not to say" },
]


export function SchemesFinderPage() {
  const [language, setLanguage] = useState<TargetLanguage>("en")
  const [profile, setProfile] = useState<WorkerProfile>({})

  const { data: listData } = useSchemesList(language)
  const match = useMatchSchemes(language)

  const actualLang = match.data?.language ?? listData?.language ?? language
  const fallback = actualLang !== language

  const set = <K extends keyof WorkerProfile>(k: K, v: WorkerProfile[K]) =>
    setProfile((p) => ({ ...p, [k]: v }))

  const submit = () => {
    match.mutate(profile)
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 md:py-10">

      {/* Header */}
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-200">
            <Landmark className="size-5" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Schemes Finder</h1>
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Answer three quick questions and see which central and state
          welfare schemes are worth checking on the official portal.
        </p>
      </header>

      {/* Disclaimer */}
      <aside
        role="note"
        aria-label="Scheme information disclaimer"
        className="rounded-lg border border-amber-200/70 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/20 px-4 py-3 text-[13px] leading-relaxed text-amber-900 dark:text-amber-100"
      >
        <span className="font-semibold">Not a guarantee of eligibility.</span>{" "}
        This list shows schemes that are worth checking based on your
        answers. The government portal decides who actually qualifies.
        Benefit amounts change; always confirm on the portal.
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
              onClick={() => setLanguage(opt.code)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition",
                language === opt.code
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

      {/* Wizard */}
      <section
        aria-label="Wizard"
        className="flex flex-col gap-5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/40 p-5"
      >
        <Question
          label="Which state do you work in?"
          value={profile.state ?? ""}
          options={STATE_OPTIONS}
          onChange={(v) => set("state", v || null)}
        />
        <Question
          label="What kind of gig work?"
          value={profile.occupation ?? ""}
          options={OCCUPATION_OPTIONS}
          onChange={(v) => set("occupation", v || null)}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Age
            </span>
            <input
              type="number"
              min={16}
              max={70}
              value={profile.age ?? ""}
              onChange={(e) =>
                set("age", e.target.value ? Number(e.target.value) : null)
              }
              placeholder="e.g. 28"
              className="rounded-md border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-3 py-2 text-sm outline-none focus:border-brand-500"
            />
          </label>
          <Question
            label="Gender"
            value={profile.gender ?? ""}
            options={GENDER_OPTIONS}
            onChange={(v) => set("gender", v || null)}
          />
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            About you
          </span>
          <Toggle
            checked={!!profile.has_bank_account}
            onToggle={(v) => set("has_bank_account", v)}
            label="I have a bank account"
          />
          <Toggle
            checked={!!profile.has_eshram}
            onToggle={(v) => set("has_eshram", v)}
            label="I am registered on e-Shram"
          />
          <Toggle
            checked={!!profile.has_daughter_under_10}
            onToggle={(v) => set("has_daughter_under_10", v)}
            label="I am the guardian of a daughter under 10"
          />
          <Toggle
            checked={!!profile.likely_means_tested_eligible}
            onToggle={(v) => set("likely_means_tested_eligible", v)}
            label="Show me schemes for lower-income households (means-tested)"
          />
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={match.isPending}
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
        >
          {match.isPending && <Loader2 className="size-4 animate-spin" />}
          Find schemes
        </button>
      </section>

      {/* Results */}
      {match.data && (
        <section aria-label="Results" className="flex flex-col gap-3">
          <div className="flex items-baseline gap-2">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-brand-700 dark:text-brand-200">
              Matches
            </div>
            <div className="text-[13px] text-muted-foreground">
              {match.data.matches.length} of {match.data.total_candidates}
              &nbsp;active schemes
            </div>
          </div>
          {match.data.matches.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No schemes matched. Try turning on the means-tested toggle
              or the e-Shram toggle to widen the results.
            </p>
          )}
          {match.data.matches.map((m) => {
            const Icon = iconFor(m.icon ?? undefined)
            return (
              <Link
                key={m.key}
                to={`/schemes/${m.key}?lang=${actualLang}`}
                className="group"
              >
                <Card className="transition group-hover:border-brand-300 dark:group-hover:border-brand-700">
                  <CardContent className="flex items-center gap-3 py-4">
                    <div className="grid size-9 place-items-center rounded-lg bg-neutral-100 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-200">
                      <Icon className="size-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[15px] font-semibold leading-tight">
                        {m.name}
                      </div>
                      {m.reasons.length > 0 && (
                        <div className="mt-1 text-[12px] text-muted-foreground">
                          {m.reasons.join(" ")}
                        </div>
                      )}
                    </div>
                    <ChevronRight className="size-4 text-muted-foreground transition group-hover:translate-x-0.5" />
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </section>
      )}

      {/* Browse all */}
      {listData && listData.schemes.length > 0 && (
        <details className="rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/40 px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-neutral-700 dark:text-neutral-200">
            Or browse all {listData.schemes.length} schemes
          </summary>
          <ul className="mt-3 flex flex-col gap-1">
            {listData.schemes.map((s) => (
              <li key={s.key}>
                <Link
                  to={`/schemes/${s.key}?lang=${actualLang}`}
                  className="flex items-center gap-2 py-1.5 text-sm text-neutral-700 dark:text-neutral-200 hover:text-brand-700 dark:hover:text-brand-200"
                >
                  <Award className="size-3.5 text-muted-foreground" />
                  {s.name}
                  {s.state_scope && s.state_scope !== "all" && (
                    <span className="ml-1 rounded-full bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5 text-[11px] text-muted-foreground">
                      {s.state_scope}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Labourline callout */}
      <aside className="mt-2 rounded-xl border border-brand-200 dark:border-brand-900/60 bg-brand-50/50 dark:bg-brand-900/15 px-4 py-4 flex items-start gap-3">
        <Phone className="mt-0.5 size-4 shrink-0 text-brand-700 dark:text-brand-300" />
        <div className="text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
          <span className="font-semibold text-neutral-900 dark:text-neutral-100">
            India Labourline · 1800-419-1550
          </span>
          <br />
          If a scheme's portal is confusing, call the helpline. They
          route to the right authority based on your situation.
        </div>
      </aside>

    </div>
  )
}


// ---------------------------------------------------------------------------
// Small controls
// ---------------------------------------------------------------------------

function Question({
  label, value, options, onChange,
}: {
  label: string
  value: string
  options: { code: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button
            key={o.code}
            type="button"
            onClick={() => onChange(value === o.code ? "" : o.code)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm transition",
              value === o.code
                ? "border-brand-500 bg-brand-50 text-brand-800 dark:border-brand-400 dark:bg-brand-900/40 dark:text-brand-100"
                : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900/40 dark:text-neutral-300",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Toggle({
  checked, onToggle, label,
}: {
  checked: boolean
  onToggle: (v: boolean) => void
  label: string
}) {
  return (
    <label className="flex items-center gap-3 cursor-pointer text-sm text-neutral-700 dark:text-neutral-300">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onToggle(e.target.checked)}
        className="size-4 accent-brand-600"
      />
      {label}
    </label>
  )
}
