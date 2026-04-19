"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarChart3, FileImage, Lightbulb, Sparkles, TrendingUp, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Dashboard</h2>
        <p className="text-muted-foreground">Your creative intelligence overview</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Active Ads" value="--" icon={FileImage} description="Across all offers" />
        <StatCard title="Winners" value="--" icon={TrendingUp} description="Above ROAS threshold" />
        <StatCard title="Seeds" value="--" icon={Lightbulb} description="In seed bank" />
        <StatCard title="Pending Questions" value="--" icon={AlertCircle} description="Need your input" />
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
          <CardTitle>Questions Needing Your Input</CardTitle>
          <CardDescription>The system has questions about your data</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No pending questions</p>
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
