"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSignUp } from "@/lib/auth/hooks";
import { ApiClientError } from "@/lib/api/client";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    .min(12, "Password must be at least 12 characters")
    .max(1024, "Password is too long"),
  full_name: z.string().max(200).optional().or(z.literal("")),
  tenant_name: z.string().max(200).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export function SignUpForm() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", full_name: "", tenant_name: "" },
  });

  const signUp = useSignUp();

  const onSubmit = handleSubmit(async (values) => {
    try {
      await signUp.mutateAsync({
        email: values.email,
        password: values.password,
        full_name: values.full_name || undefined,
        tenant_name: values.tenant_name || undefined,
      });
      router.replace("/home");
    } catch {
      // displayed via signUp.error below
    }
  });

  const apiError = signUp.error instanceof ApiClientError ? signUp.error : null;

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
      {apiError ? (
        <Alert variant="destructive">
          <AlertTitle>Sign-up failed</AlertTitle>
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
        {errors.email ? <p className="text-xs text-destructive">{errors.email.message}</p> : null}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="new-password"
          aria-invalid={errors.password ? "true" : "false"}
          {...register("password")}
        />
        {errors.password ? (
          <p className="text-xs text-destructive">{errors.password.message}</p>
        ) : null}
        <p className="text-2xs text-muted-foreground">At least 12 characters.</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="full_name">Full name (optional)</Label>
        <Input id="full_name" autoComplete="name" {...register("full_name")} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="tenant_name">Workspace name (optional)</Label>
        <Input id="tenant_name" {...register("tenant_name")} />
        <p className="text-2xs text-muted-foreground">
          We&apos;ll derive a name from your email if you leave this blank.
        </p>
      </div>

      <Button type="submit" loading={isSubmitting} disabled={isSubmitting}>
        Create account
      </Button>
    </form>
  );
}
