"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarChart3, FileImage, Lightbulb, Sparkles, TrendingUp, AlertCircle, RefreshCw, Activity, CheckCircle2, Clock } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { performance, dashboard, workflows, approvals } from "@/lib/api";

export default function DashboardPage() {
  const token = useAuth((s) => s.token);
  const workspaceId = useAuth((s) => s.activeWorkspaceId);
  const [summary, setSummary] = useState<any>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [activeWorkflows, setActiveWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !workspaceId) return;
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [token, workspaceId]);

  async function loadData() {
    if (!token || !workspaceId) return;
    setLoading(true);
    try {
      const [s, q, w] = await Promise.all([
        dashboard.summary(token, workspaceId).catch(() => null),
        performance.getQuestions(token, workspaceId).catch(() => []),
        workflows.active(token, workspaceId).catch(() => []),
      ]);
      setSummary(s);
      setQuestions(q || []);
      setActiveWorkflows(w || []);
    } finally {
      setLoading(false);
    }
  }

  async function handleSyncLearning() {
    if (!token || !workspaceId) return;
    try {
      await performance.syncLearning(token, workspaceId);
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  }

  async function handleAnswer(questionId: string, answer: string) {
    if (!token || !workspaceId) return;
    try {
      await performance.answerQuestion(token, workspaceId, questionId, { answer });
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Dashboard</h2>
          <p className="text-muted-foreground">Your creative intelligence overview</p>
        </div>
        <Button variant="outline" onClick={handleSyncLearning}>
          <RefreshCw className="mr-2 h-4 w-4" /> Sync Learning
        </Button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Ads"
          value={summary?.active_ads ?? "--"}
          icon={FileImage}
          description="Across all offers"
          loading={loading && !summary}
        />
        <StatCard
          title="Winners"
          value={summary?.winners ?? "--"}
          icon={TrendingUp}
          description="Above winning threshold"
          accent={summary?.winners > 0 ? "green" : undefined}
          loading={loading && !summary}
        />
        <StatCard
          title="Pending Approvals"
          value={summary?.pending_approvals ?? "--"}
          icon={CheckCircle2}
          description="Angles & briefs to review"
          accent={summary?.pending_approvals > 0 ? "yellow" : undefined}
          loading={loading && !summary}
          href="/approvals"
        />
        <StatCard
          title="Pending Questions"
          value={loading && !summary ? "..." : (summary?.pending_questions ?? questions.length)}
          icon={AlertCircle}
          description="Need your input"
          accent={questions.length > 0 ? "yellow" : undefined}
          loading={loading && !summary}
        />
      </div>

      {/* Active Workflows */}
      {activeWorkflows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-blue-500" />
              Active Workflows ({activeWorkflows.length})
            </CardTitle>
            <CardDescription>Currently running cycles</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {activeWorkflows.map((w: any) => (
                <div
                  key={w.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Clock className="h-4 w-4 animate-pulse text-blue-500" />
                    <div>
                      <p className="text-sm font-medium">{w.workflow_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-muted-foreground">
                        {w.offer_id ? `Offer: ${w.offer_id} · ` : ""}
                        {new Date(w.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full bg-blue-900/30 px-2 py-0.5 text-xs text-blue-300">
                    {w.state}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Performance</CardTitle>
            <CardDescription>Upload metrics from Ad Audit or Bulk Launcher</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/performance">
              <Button className="w-full">Upload Performance Data</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Creative Library</CardTitle>
            <CardDescription>Browse, search, and study your creative assets</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/creative-library">
              <Button variant="secondary" className="w-full">Browse Library</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Approvals</CardTitle>
            <CardDescription>Review angles and briefs before writing runs</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/approvals">
              <Button variant="secondary" className="w-full">
                Review Outputs
                {summary?.pending_approvals > 0 && (
                  <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                    {summary.pending_approvals}
                  </span>
                )}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Pending Questions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-yellow-500" />
            Questions Needing Your Input
          </CardTitle>
          <CardDescription>The system has questions about your data</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : questions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pending questions</p>
          ) : (
            <div className="space-y-3">
              {questions.map((q: any) => (
                <div key={q.id} className="rounded-lg border p-4">
                  <p className="text-sm font-medium">{q.question}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">{q.question_type}</span>
                    {q.options && q.options.map((opt: string) => (
                      <Button
                        key={opt}
                        size="sm"
                        variant="outline"
                        onClick={() => handleAnswer(q.id, opt)}
                      >
                        {opt.replace(/_/g, " ")}
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  accent,
  loading,
  href,
}: {
  title: string;
  value: string | number;
  icon: any;
  description: string;
  accent?: "green" | "yellow" | "red";
  loading?: boolean;
  href?: string;
}) {
  const accentColor = accent === "green"
    ? "text-green-500"
    : accent === "yellow"
    ? "text-yellow-500"
    : accent === "red"
    ? "text-red-500"
    : "text-muted-foreground";

  const card = (
    <Card className={href ? "cursor-pointer transition-colors hover:border-primary" : ""}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={`h-4 w-4 ${accentColor}`} />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{loading ? "..." : value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );

  return href ? <Link href={href}>{card}</Link> : card;
}
