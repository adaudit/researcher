"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle, XCircle, Clock, TrendingUp } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { approvals } from "@/lib/api";

const TABS = [
  { label: "All Pending", type: undefined },
  { label: "Angles", type: "angle_approval" },
  { label: "Briefs", type: "brief_approval" },
  { label: "Concepts", type: "concept_approval" },
  { label: "Reflections", type: "reflection_approval" },
];

export default function ApprovalsPage() {
  const token = useAuth((s) => s.token);
  const workspaceId = useAuth((s) => s.activeWorkspaceId);
  const [items, setItems] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [rejectionText, setRejectionText] = useState("");
  const [deciding, setDeciding] = useState<string | null>(null);

  useEffect(() => {
    if (token && workspaceId) load();
  }, [token, workspaceId, activeTab]);

  async function load() {
    if (!token || !workspaceId) return;
    setLoading(true);
    try {
      const data = await approvals.list(
        token, workspaceId, "pending", TABS[activeTab].type,
      );
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleDecision(id: string, action: "approve" | "reject") {
    if (!token || !workspaceId) return;
    setDeciding(id);
    try {
      await approvals.decide(
        token, workspaceId, id, action,
        action === "reject" ? rejectionText : undefined,
      );
      setRejecting(null);
      setRejectionText("");
      await load();
    } catch (e: any) {
      alert(e.message || "Failed to process decision");
    } finally {
      setDeciding(null);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Approvals</h2>
        <p className="text-muted-foreground">
          Review angle ideas and briefs before copy generation runs
        </p>
      </div>

      {/* Tab filters */}
      <div className="flex gap-2 border-b pb-2">
        {TABS.map((tab, i) => (
          <Button
            key={tab.label}
            variant="ghost"
            className={`rounded-none ${i === activeTab ? "border-b-2 border-primary" : ""}`}
            onClick={() => setActiveTab(i)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Approval items */}
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : items.length === 0 ? (
        <Card className="flex items-center justify-center p-12">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-lg font-medium">Nothing pending</p>
            <p className="text-sm text-muted-foreground">
              Ideation outputs will appear here for review before copy generation runs
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Clock className="h-4 w-4 text-yellow-500" />
                      {item.approval_type.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </CardTitle>
                    <CardDescription>
                      {item.offer_id && `Offer: ${item.offer_id}`}
                      {" "}
                      {new Date(item.created_at).toLocaleDateString()}
                    </CardDescription>
                  </div>

                  {/* Grade trajectory if available */}
                  {item.payload?.grade_trajectory && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <TrendingUp className="h-3 w-3" />
                      {item.payload.grade_trajectory.map((g: any, i: number) => (
                        <span
                          key={i}
                          className={`rounded px-1 ${g.score >= 7 ? "bg-green-900/30 text-green-400" : g.score >= 5 ? "bg-yellow-900/30 text-yellow-400" : "bg-red-900/30 text-red-400"}`}
                        >
                          {g.score.toFixed(1)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Payload preview */}
                <div className="max-h-60 overflow-auto rounded-md bg-muted/50 p-3">
                  <pre className="whitespace-pre-wrap text-xs">
                    {JSON.stringify(item.payload, null, 2)?.slice(0, 2000)}
                  </pre>
                </div>

                {/* Actions */}
                {rejecting === item.id ? (
                  <div className="space-y-2">
                    <textarea
                      className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                      rows={3}
                      placeholder="Why are you rejecting? This feedback will be used to improve the next iteration..."
                      value={rejectionText}
                      onChange={(e) => setRejectionText(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={!rejectionText.trim() || deciding === item.id}
                        onClick={() => handleDecision(item.id, "reject")}
                      >
                        {deciding === item.id ? "Rejecting..." : "Confirm Reject"}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setRejecting(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={deciding === item.id}
                      onClick={() => handleDecision(item.id, "approve")}
                    >
                      <CheckCircle className="mr-2 h-4 w-4" />
                      {deciding === item.id ? "Approving..." : "Approve"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setRejecting(item.id)}
                    >
                      <XCircle className="mr-2 h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
