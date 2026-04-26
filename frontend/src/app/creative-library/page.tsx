"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileImage, Search, Filter, Plus } from "lucide-react";

const FILTER_OPTIONS = {
  format_type: ["headline_plus_image", "before_after", "meme_style", "ugc_selfie", "talking_head_ugc", "listicle_video", "story_carousel"],
  hook_type: ["pain_point", "curiosity", "contrarian", "story", "proof_led", "identity", "consequence"],
  awareness_level: ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"],
  performance_tier: ["winner", "strong", "average", "weak", "loser", "untested"],
  ownership: ["own", "competitor", "swipe", "reference"],
};

export default function CreativeLibraryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [showFilters, setShowFilters] = useState(false);

  function toggleFilter(key: string, value: string) {
    setActiveFilters((prev) => {
      if (prev[key] === value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Creative Library</h2>
          <p className="text-muted-foreground">Browse, search, and study creative assets</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline"><Plus className="mr-2 h-4 w-4" />Add Swipe</Button>
          <Button><Plus className="mr-2 h-4 w-4" />Ingest Creative</Button>
        </div>
      </div>

      {/* Search + Filter Bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search creatives by text, hook, angle..."
            className="pl-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <Button variant="outline" onClick={() => setShowFilters(!showFilters)}>
          <Filter className="mr-2 h-4 w-4" />
          Filters {Object.keys(activeFilters).length > 0 && `(${Object.keys(activeFilters).length})`}
        </Button>
        <Button variant="outline">Find Similar</Button>
      </div>

      {/* Filter chips */}
      {showFilters && (
        <Card>
          <CardContent className="space-y-4 pt-4">
            {Object.entries(FILTER_OPTIONS).map(([key, values]) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-medium uppercase text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </label>
                <div className="flex flex-wrap gap-1">
                  {values.map((value) => (
                    <button
                      key={value}
                      onClick={() => toggleFilter(key, value)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                        activeFilters[key] === value
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground hover:bg-accent"
                      }`}
                    >
                      {value.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Results Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Empty state */}
        <Card className="col-span-full flex h-64 items-center justify-center">
          <div className="text-center">
            <FileImage className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-lg font-medium">No creatives yet</p>
            <p className="text-sm text-muted-foreground">Ingest creatives or add swipes to build your library</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
