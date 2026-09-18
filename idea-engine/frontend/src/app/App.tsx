import { AppRouter } from "@/app/router";
import { Providers } from "@/app/providers";

export function App() {
  return (
    <Providers>
      <AppRouter />
    </Providers>
  );
}