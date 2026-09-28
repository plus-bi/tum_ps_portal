import "./globals.css";
import {ClerkProvider} from "@clerk/nextjs";
import {Inter, Space_Grotesk} from "next/font/google";

const body = Inter({subsets: ["latin"], variable: "--font-body", display: "swap"});
const heading = Space_Grotesk({subsets: ["latin"], variable: "--font-heading", display: "swap"});

const clerkAppearance = {
  variables: {
    colorPrimary: "#00d6a8", colorTextOnPrimaryBackground: "#0d1220", colorBackground: "#1c2333",
    colorText: "#eef2f7", colorTextSecondary: "#96a0b3", colorInputBackground: "#141b29", colorInputText: "#eef2f7",
    colorNeutral: "#eef2f7", borderRadius: "0.75rem", fontFamily: "var(--font-body)",
  },
};

export const metadata = {title: "Project Opportunities from TU Munich", description: "Find active Project Studies and Informatics IDPs across audited TUM sources."};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en" className={`${body.variable} ${heading.variable}`}><body><ClerkProvider appearance={clerkAppearance}>{children}</ClerkProvider></body></html>;
}
