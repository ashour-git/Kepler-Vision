"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSignIn } from "@/lib/auth/hooks";
import { ApiClientError } from "@/lib/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

export function SignInForm() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const signIn = useSignIn();

  const onSubmit = handleSubmit(async (values) => {
    try {
      await signIn.mutateAsync({ email: values.email, password: values.password });
      router.replace("/home");
    } catch (err) {
      // Mutation error is exposed via signIn.error; the alert below renders it.
      // We re-throw nothing; the form stays interactive.
      void err;
    }
  });

  const apiError = signIn.error instanceof ApiClientError ? signIn.error : null;
  const fieldErrors = apiError?.details?.fields as Record<string, string[]> | undefined;

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
      {apiError ? (
        <Alert variant="destructive">
          <AlertTitle>{humanTitle(apiError.code)}</AlertTitle>
          <AlertDescription>{apiError.message}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          aria-invalid={errors.email ? "true" : "false"}
          {...register("email")}
        />
        {errors.email ? (
          <p className="text-xs text-destructive">{errors.email.message}</p>
        ) : null}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={errors.password ? "true" : "false"}
          {...register("password")}
        />
        {errors.password ? (
          <p className="text-xs text-destructive">{errors.password.message}</p>
        ) : null}
        {fieldErrors?.password ? (
          <p className="text-xs text-destructive">{fieldErrors.password.join(" ")}</p>
        ) : null}
      </div>

      <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
        Sign in
      </Button>

      <p className="text-center text-xs text-muted-foreground">
        Don&apos;t have an account?{" "}
        <a href="/sign-up" className="text-primary hover:underline">
          Create one
        </a>
      </p>
    </form>
  );
}

function humanTitle(code: string): string {
  switch (code) {
    case "invalid_credentials":
      return "Sign-in failed";
    case "account_locked":
      return "Account locked";
    case "account_disabled":
      return "Account disabled";
    case "rate_limited":
      return "Too many attempts";
    default:
      return "Error";
  }
}
