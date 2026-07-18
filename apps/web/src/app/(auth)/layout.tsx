export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12 focus:outline-none"
      >
        {children}
      </main>
    </div>
  );
}
