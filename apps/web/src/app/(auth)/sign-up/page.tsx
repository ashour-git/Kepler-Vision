"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { SignUpForm } from "@/components/forms/sign-up-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession } from "@/lib/auth/hooks";

export default function SignUpPage() {
  const router = useRouter();
  const session = useSession();

  useEffect(() => {
    if (session) {
      router.replace("/home");
    }
  }, [session, router]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <p className="text-sm text-muted-foreground">
          We&apos;ll spin up a workspace for you automatically.
        </p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>Get started</CardTitle>
          <CardDescription>You&apos;ll be the owner of a new workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          <SignUpForm />
        </CardContent>
      </Card>
      <p className="text-center text-xs text-muted-foreground">
        Already have an account?{" "}
        <a href="/sign-in" className="text-primary hover:underline">
          Sign in
        </a>
      </p>
    </div>
  );
}
