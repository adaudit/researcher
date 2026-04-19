"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div>
        <h2 className="text-3xl font-bold">Settings</h2>
        <p className="text-muted-foreground">Workspace and account configuration</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Winning Definitions</CardTitle>
          <CardDescription>What counts as "winning" for this account</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted-foreground">Primary metric</label>
              <select className="w-full rounded-md border bg-background px-3 py-2 text-sm">
                <option value="roas">ROAS</option>
                <option value="cpa">CPA</option>
                <option value="tp_roas">Third-party ROAS</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Attribution source</label>
              <select className="w-full rounded-md border bg-background px-3 py-2 text-sm">
                <option value="first_party">First-party</option>
                <option value="third_party">Third-party</option>
                <option value="blended">Blended</option>
              </select>
            </div>
          </div>
          <Button>Save Winning Definitions</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>Connected services</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-xs text-muted-foreground">ScrapCreators API Key</label>
            <Input type="password" placeholder="Enter API key..." />
          </div>
          <Button>Save API Keys</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Team Members</CardTitle>
          <CardDescription>Manage workspace access</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button variant="outline">Invite Member</Button>
        </CardContent>
      </Card>
    </div>
  );
}
