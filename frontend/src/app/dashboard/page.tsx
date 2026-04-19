"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarChart3, FileImage, Lightbulb, Sparkles, TrendingUp, AlertCircle, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { performance, creativeLibrary } from "@/lib/api";

export default function DashboardPage() {
  const token = useAuth((s) => s.token);
  const workspaceId = useAuth((s) => s.activeWorkspaceId);
  const [questions, setQuestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !workspaceId) return;
    loadData();
  }, [token, workspaceId]);

  async function loadData() {
    setLoading(true);
    try {
      const q = await performance.getQuestions(token!, workspaceId!);
      setQuestions(q);
    } catch {
      // API not available yet — show empty state
    }
    setLoading(false);
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
        <StatCard title="Active Ads" value="--" icon={FileImage} description="Across all offers" />
        <StatCard title="Winners" value="--" icon={TrendingUp} description="Above ROAS threshold" />
        <StatCard title="Seeds" value="--" icon={Lightbulb} description="In seed bank" />
        <StatCard
          title="Pending Questions"
          value={loading ? "..." : String(questions.length)}
          icon={AlertCircle}
          description="Need your input"
        />
      </div>

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
            <CardTitle className="text-lg">Generate Creative</CardTitle>
            <CardDescription>Run the full cycle: ideation, brief, writing, creative</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/approvals">
              <Button variant="secondary" className="w-full">View Outputs</Button>
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
                      <Button key={opt} size="sm" variant="outline" onClick={async () => {
                        try {
                          await performance.answerQuestion(token!, workspaceId!, q.id, { answer: opt });
                          loadData();
                        } catch {}
                      }}>
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

function StatCard({ title, value, icon: Icon, description }: {
  title: string; value: string; icon: any; description: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
