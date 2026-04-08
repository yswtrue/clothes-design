export default function DashboardPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black px-4">
      <div className="text-center">
        <h1 className="text-3xl font-semibold text-zinc-950 dark:text-zinc-50 mb-4">
          Dashboard
        </h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          This is a protected route. You must be logged in to see this.
        </p>
      </div>
    </div>
  );
}
