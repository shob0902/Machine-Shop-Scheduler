export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-gray-500">
      <div className="mb-4 h-10 w-10 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
      <p className="text-lg">{label}</p>
    </div>
  );
}

export function ErrorBanner({ message, suggestion }: { message: string; suggestion?: string }) {
  return (
    <div className="rounded-xl border-2 border-red-300 bg-red-50 p-6 text-red-800">
      <p className="text-lg font-bold">Something went wrong</p>
      <p className="mt-1">{message}</p>
      {suggestion && <p className="mt-2 text-sm text-red-700">Suggestion: {suggestion}</p>}
    </div>
  );
}
