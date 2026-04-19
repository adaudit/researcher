"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle, XCircle, Edit, Eye } from "lucide-react";

export default function ApprovalsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Approvals</h2>
        <p className="text-muted-foreground">Review and approve generated creative outputs</p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button variant="ghost" className="rounded-none border-b-2 border-primary">All Pending</Button>
        <Button variant="ghost" className="rounded-none">Hooks</Button>
        <Button variant="ghost" className="rounded-none">Copy</Button>
        <Button variant="ghost" className="rounded-none">Headlines</Button>
        <Button variant="ghost" className="rounded-none">Image Concepts</Button>
        <Button variant="ghost" className="rounded-none">Briefs</Button>
      </div>

      {/* Pending items */}
      <div className="space-y-4">
        <Card className="flex items-center justify-center p-12">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-lg font-medium">Nothing pending</p>
            <p className="text-sm text-muted-foreground">
              Run a creative cycle to generate outputs for review
            </p>
            <Button className="mt-4">Run Full Cycle</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
