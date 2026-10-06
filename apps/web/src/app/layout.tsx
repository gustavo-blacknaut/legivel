import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@/styles/tokens.css";
import "@/styles/base.css";
import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";
import { Providers } from "@/components/Providers";
import { loadInstance } from "@/lib/instance";
import { NONCE_HEADER } from "@/lib/security-headers";
import { isThemePreference, themeBootScript } from "@/lib/theme";

export async function generateMetadata(): Promise<Metadata> {
  const instance = await loadInstance();
  return {
    title: { default: instance.name, template: `%s · ${instance.name}` },
    icons: { icon: instance.logo_url ?? "/favicon.svg" },
    robots: { index: false, follow: false },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f6" },
    { media: "(prefers-color-scheme: dark)", color: "#111513" },
  ],
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const instance = await loadInstance();
  const theme = isThemePreference(instance.default_theme) ? instance.default_theme : "system";
  const nonce = (await headers()).get(NONCE_HEADER) ?? undefined;
  return (
    <html lang={instance.default_language} suppressHydrationWarning>
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: themeBootScript(theme) }} />
      </head>
      <body>
        <Providers instance={instance}>{children}</Providers>
      </body>
    </html>
  );
}
