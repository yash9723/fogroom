"use client";

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster, toast } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PresentationSync } from "@/components/layout/presentation-sync";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            refetchOnWindowFocus: false,
            retry: (count, error) => {
              if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false;
              return count < 2;
            },
          },
        },
        queryCache: new QueryCache({
          onError: (error, query) => {
            if (query.meta?.silent) return;
            if (error instanceof ApiError && error.status === 401) return;
            toast.error(error instanceof ApiError ? error.message : "Request failed", {
              id: `q-${error instanceof ApiError ? error.code : "error"}`,
            });
          },
        }),
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={250}>
        <PresentationSync />
        {children}
        <Toaster theme="dark" position="top-right" richColors closeButton />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
