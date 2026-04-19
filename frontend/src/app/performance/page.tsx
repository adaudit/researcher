"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, BarChart3, AlertCircle, TrendingUp } from "lucide-react";

export default function PerformancePage() {
  const [uploadMode, setUploadMode] = useState<"paste" | "file" | null>(null);
  const [pasteData, setPasteData] = useState("");

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Performance Intelligence</h2>
        <p className="text-muted-foreground">Upload metrics from Ad Audit or Bulk Launcher</p>
      </div>

      {/* Upload Section */}
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

      {uploadMode === "paste" && (
        <Card>
          <CardHeader>
            <CardTitle>Paste Performance Data</CardTitle>
            <CardDescription>
              Paste CSV or JSON from Ad Audit / Bulk Launcher. The system will auto-detect the format
              and ask clarifying questions if anything is ambiguous.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              className="h-64 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
              placeholder="Paste your performance data here..."
              value={pasteData}
              onChange={(e) => setPasteData(e.target.value)}
            />
            <div className="flex gap-2">
              <Button>Process Data</Button>
              <Button variant="outline" onClick={() => setUploadMode(null)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {uploadMode === "file" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload File</CardTitle>
            <CardDescription>Drag and drop or select a CSV/JSON file</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-40 items-center justify-center rounded-lg border-2 border-dashed">
              <div className="text-center">
                <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">Drop file here or click to browse</p>
                <input type="file" className="absolute inset-0 cursor-pointer opacity-0" accept=".csv,.json" />
              </div>
            </div>
            <Button variant="outline" className="mt-4" onClick={() => setUploadMode(null)}>Cancel</Button>
          </CardContent>
        </Card>
      )}

      {/* Pending Questions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-yellow-500" />
            Clarifying Questions
          </CardTitle>
          <CardDescription>The system needs your input on these data points</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No pending questions. Upload data to get started.</p>
        </CardContent>
      </Card>

      {/* Performance Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Performance Overview
          </CardTitle>
          <CardDescription>Winning and losing creatives by performance tier</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No performance data yet. Upload data above.</p>
        </CardContent>
      </Card>
    </div>
  );
}
