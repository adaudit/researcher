"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, AlertCircle, TrendingUp, CheckCircle } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { performance } from "@/lib/api";

export default function PerformancePage() {
  const token = useAuth((s) => s.token);
  const workspaceId = useAuth((s) => s.activeWorkspaceId);
  const [uploadMode, setUploadMode] = useState<"paste" | "file" | null>(null);
  const [pasteData, setPasteData] = useState("");
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (token && workspaceId) loadQuestions();
  }, [token, workspaceId]);

  async function loadQuestions() {
    try {
      const q = await performance.getQuestions(token!, workspaceId!);
      setQuestions(q);
    } catch {}
  }

  async function processData() {
    if (!token || !workspaceId || !pasteData.trim()) return;
    setProcessing(true);
    setError("");
    setResult(null);

    try {
      // Try to parse as JSON first, then CSV
      let records: any[] = [];

      try {
        const parsed = JSON.parse(pasteData);
        records = Array.isArray(parsed) ? parsed : parsed.records || parsed.data || [parsed];
      } catch {
        // Parse as CSV
        const lines = pasteData.trim().split("\n");
        if (lines.length < 2) throw new Error("Need at least a header row and one data row");

        const headers = lines[0].split(",").map((h) => h.trim().replace(/"/g, ""));
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(",").map((v) => v.trim().replace(/"/g, ""));
          const row: Record<string, any> = {};
          headers.forEach((h, j) => {
            const val = values[j];
            if (val && !isNaN(Number(val))) row[h] = Number(val);
            else row[h] = val || null;
          });
          // Map common CSV column names to our schema
          records.push({
            external_ad_id: row.ad_id || row.Ad_ID || row["Ad ID"] || row.id || `row_${i}`,
            external_adset_id: row.adset_id || row["Ad Set ID"] || null,
            external_campaign_id: row.campaign_id || row["Campaign ID"] || null,
            ad_name: row.ad_name || row["Ad Name"] || row.name || null,
            date: row.date || row.Date || row.day || new Date().toISOString().split("T")[0],
            spend: row.spend || row.Spend || row["Amount Spent"] || null,
            impressions: row.impressions || row.Impressions || null,
            clicks: row.clicks || row.Clicks || row["Link Clicks"] || null,
            purchases: row.purchases || row.Purchases || row.conversions || null,
            purchase_value: row.purchase_value || row.revenue || row.Revenue || row["Purchase Value"] || null,
            hook_rate: row.hook_rate || row["Hook Rate"] || null,
            thumb_stop_ratio: row.thumb_stop_ratio || row["Thumb Stop"] || null,
            tp_roas: row.tp_roas || row["3P ROAS"] || null,
            tp_cpa: row.tp_cpa || row["3P CPA"] || null,
            tp_purchases: row.tp_purchases || row["3P Purchases"] || null,
            tp_revenue: row.tp_revenue || row["3P Revenue"] || null,
          });
        }
      }

      const res = await performance.ingestSnapshots(token, workspaceId, {
        data_source: "bulk_launcher",
        records,
      });
      setResult(res);
      await loadQuestions();
    } catch (e: any) {
      setError(e.message || "Failed to process data");
    } finally {
      setProcessing(false);
    }
  }

  async function answerQuestion(questionId: string, answer: string) {
    if (!token || !workspaceId) return;
    try {
      await performance.answerQuestion(token, workspaceId, questionId, {
        answer,
        creates_rule: true,
      });
      await loadQuestions();
    } catch {}
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Performance Intelligence</h2>
        <p className="text-muted-foreground">Upload metrics from Ad Audit or Bulk Launcher</p>
      </div>

      {/* Upload Section */}
      {!uploadMode && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Card className="cursor-pointer hover:border-primary" onClick={() => setUploadMode("paste")}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Upload className="h-5 w-5" /> Paste CSV / JSON
              </CardTitle>
              <CardDescription>Paste performance data directly from your export</CardDescription>
            </CardHeader>
          </Card>

          <Card className="cursor-pointer hover:border-primary" onClick={() => setUploadMode("file")}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Upload className="h-5 w-5" /> Upload File
              </CardTitle>
              <CardDescription>Upload a CSV or JSON export file</CardDescription>
            </CardHeader>
          </Card>
        </div>
      )}

      {uploadMode === "paste" && (
        <Card>
          <CardHeader>
            <CardTitle>Paste Performance Data</CardTitle>
            <CardDescription>
              Paste CSV or JSON from Ad Audit / Bulk Launcher. The system will auto-detect the format,
              calculate derived metrics, classify performance tiers, and ask clarifying questions if anything is ambiguous.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              className="h-64 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
              placeholder={"Paste CSV (with headers) or JSON array...\n\nCSV example:\nad_id,ad_name,date,spend,impressions,clicks,purchases,purchase_value\nad_001,My Ad,2026-04-15,150.00,12000,240,8,392.00"}
              value={pasteData}
              onChange={(e) => setPasteData(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            {result && (
              <div className="rounded-lg border border-green-800 bg-green-900/20 p-4">
                <p className="flex items-center gap-2 text-sm font-medium text-green-400">
                  <CheckCircle className="h-4 w-4" /> Processed {result.ingested} records
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Winners: {result.winners_found} | Questions: {result.questions_generated} | Anomalies: {result.anomalies_flagged}
                </p>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={processData} disabled={processing || !pasteData.trim()}>
                {processing ? "Processing..." : "Process Data"}
              </Button>
              <Button variant="outline" onClick={() => { setUploadMode(null); setResult(null); setError(""); }}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pending Questions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-yellow-500" />
            Clarifying Questions ({questions.length})
          </CardTitle>
          <CardDescription>The system needs your input on these data points</CardDescription>
        </CardHeader>
        <CardContent>
          {questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pending questions.</p>
          ) : (
            <div className="space-y-4">
              {questions.map((q: any) => (
                <div key={q.id} className="rounded-lg border p-4">
                  <p className="text-sm font-medium">{q.question}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">{q.question_type}</span>
                    {q.options ? (
                      q.options.map((opt: string) => (
                        <Button key={opt} size="sm" variant="outline" onClick={() => answerQuestion(q.id, opt)}>
                          {opt.replace(/_/g, " ")}
                        </Button>
                      ))
                    ) : (
                      <div className="flex flex-1 gap-2">
                        <input
                          className="flex-1 rounded-md border bg-background px-2 py-1 text-sm"
                          placeholder="Type your answer..."
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              answerQuestion(q.id, (e.target as HTMLInputElement).value);
                            }
                          }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <Button
          variant="outline"
          onClick={async () => {
            if (token && workspaceId) {
              await performance.syncLearning(token, workspaceId);
              alert("Learning sync triggered — skills and primers updating");
            }
          }}
        >
          <TrendingUp className="mr-2 h-4 w-4" /> Sync Learning from Winners
        </Button>
        <Button variant="outline" onClick={async () => {
          const benchmarks = await performance.getBenchmarks(prompt("Industry?") || "supplements");
          alert(JSON.stringify(benchmarks, null, 2));
        }}>
          View Industry Benchmarks
        </Button>
      </div>
    </div>
  );
}
