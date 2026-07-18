import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DashboardClient } from "./client";

export const metadata = { title: "Home" };

export default function HomePage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="text-sm text-muted-foreground">
          Welcome to Kepler Vision. Sprint 1 ships authentication and identity — more
          is on the way.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Your account</CardTitle>
          <CardDescription>Identity and workspace information from the API.</CardDescription>
        </CardHeader>
        <CardContent>
          <DashboardClient />
        </CardContent>
      </Card>
    </div>
  );
}
