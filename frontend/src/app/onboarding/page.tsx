"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  { id: "brand", title: "Brand Setup", description: "Tell us about the brand" },
  { id: "offer", title: "Offer Details", description: "Product, mechanism, audience" },
  { id: "links", title: "Links & Assets", description: "Landing pages, ad accounts, competitors" },
  { id: "primers", title: "Primers", description: "Upload winning ads, hooks, headlines" },
  { id: "benchmarks", title: "Benchmarks", description: "Set winning definitions" },
  { id: "launch", title: "Launch", description: "Start the first analysis cycle" },
];

const INDUSTRIES = [
  "supplements", "skincare", "fitness", "ecommerce_general", "saas",
  "financial_services", "education", "food_beverage", "fashion",
  "home_garden", "pets", "beauty", "cbd_wellness", "info_products",
];

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Record<string, string>>({});

  const current = STEPS[step];

  function updateForm(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-8">
      {/* Progress */}
      <div className="flex gap-2">
        {STEPS.map((s, i) => (
          <div key={s.id} className={`h-2 flex-1 rounded-full ${i <= step ? "bg-primary" : "bg-muted"}`} />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{current.title}</CardTitle>
          <CardDescription>{current.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 0 && (
            <>
              <Input placeholder="Brand name" value={form.brand_name || ""} onChange={(e) => updateForm("brand_name", e.target.value)} />
              <Input placeholder="Website URL" value={form.website || ""} onChange={(e) => updateForm("website", e.target.value)} />
              <div>
                <label className="mb-2 block text-sm font-medium">Industry</label>
                <select
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  value={form.industry || ""}
                  onChange={(e) => updateForm("industry", e.target.value)}
                >
                  <option value="">Select industry...</option>
                  {INDUSTRIES.map((ind) => (
                    <option key={ind} value={ind}>{ind.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <Input placeholder="Product name" value={form.product || ""} onChange={(e) => updateForm("product", e.target.value)} />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={3}
                placeholder="Mechanism — how does the product actually work?"
                value={form.mechanism || ""}
                onChange={(e) => updateForm("mechanism", e.target.value)}
              />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={3}
                placeholder="Target audience — who is this for?"
                value={form.target_audience || ""}
                onChange={(e) => updateForm("target_audience", e.target.value)}
              />
              <Input placeholder="Price point" value={form.price || ""} onChange={(e) => updateForm("price", e.target.value)} />
            </>
          )}

          {step === 2 && (
            <>
              <Input placeholder="Landing page URL" value={form.landing_page || ""} onChange={(e) => updateForm("landing_page", e.target.value)} />
              <Input placeholder="Product page URL" value={form.pdp_url || ""} onChange={(e) => updateForm("pdp_url", e.target.value)} />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={2}
                placeholder="Competitor brands (one per line)"
                value={form.competitors || ""}
                onChange={(e) => updateForm("competitors", e.target.value)}
              />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={2}
                placeholder="Competitor ad library links (one per line)"
                value={form.competitor_links || ""}
                onChange={(e) => updateForm("competitor_links", e.target.value)}
              />
            </>
          )}

          {step === 3 && (
            <>
              <p className="text-sm text-muted-foreground">
                Paste your best-performing ads below. 10-12 winning ads separated by ### gives the system the best calibration.
                If you are starting fresh, paste competitor swipes or the best ads you can find in the space.
              </p>
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={6}
                placeholder="Paste winning ads separated by ### ..."
                value={form.ad_primer || ""}
                onChange={(e) => updateForm("ad_primer", e.target.value)}
              />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={4}
                placeholder="Paste winning hooks (one per line or ### separated)..."
                value={form.hook_primer || ""}
                onChange={(e) => updateForm("hook_primer", e.target.value)}
              />
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                rows={4}
                placeholder="Paste winning headlines (one per line or ### separated)..."
                value={form.headline_primer || ""}
                onChange={(e) => updateForm("headline_primer", e.target.value)}
              />
            </>
          )}

          {step === 4 && (
            <>
              <p className="text-sm text-muted-foreground">
                What counts as "winning" for this brand? Set thresholds for performance tiers.
                Industry benchmarks are pre-loaded based on your selection.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-muted-foreground">Winner ROAS</label>
                  <Input type="number" step="0.1" value={form.winner_roas || "3.0"} onChange={(e) => updateForm("winner_roas", e.target.value)} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Strong ROAS</label>
                  <Input type="number" step="0.1" value={form.strong_roas || "2.0"} onChange={(e) => updateForm("strong_roas", e.target.value)} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Target CPA</label>
                  <Input type="number" step="1" value={form.target_cpa || "45"} onChange={(e) => updateForm("target_cpa", e.target.value)} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Min spend to evaluate</label>
                  <Input type="number" step="10" value={form.min_spend || "50"} onChange={(e) => updateForm("min_spend", e.target.value)} />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Attribution source</label>
                <select
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  value={form.attribution || "first_party"}
                  onChange={(e) => updateForm("attribution", e.target.value)}
                >
                  <option value="first_party">First-party (Meta reported)</option>
                  <option value="third_party">Third-party (Ad Audit / Bulk Launcher)</option>
                  <option value="blended">Blended average</option>
                </select>
              </div>
            </>
          )}

          {step === 5 && (
            <div className="space-y-4 text-center">
              <div className="text-6xl">🚀</div>
              <p className="text-lg font-medium">Ready to launch the first analysis cycle</p>
              <p className="text-sm text-muted-foreground">
                The system will analyze the offer, decompose the landing page, mine VOC,
                build proof inventory, map differentiation, engineer hooks, and compose briefs.
              </p>
              <Button size="lg" className="mt-4">Launch Analysis</Button>
            </div>
          )}

          {step < STEPS.length - 1 && (
            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
                Back
              </Button>
              <Button onClick={() => setStep(step + 1)}>Continue</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
