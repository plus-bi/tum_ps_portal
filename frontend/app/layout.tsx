import "./globals.css";
import {Inter, Space_Grotesk} from "next/font/google";
import AnalyticsConsent from "./AnalyticsConsent";
import {CatalogProvider} from "./CatalogProvider";
import ContactPill from "./ContactPill";

const body = Inter({subsets: ["latin"], variable: "--font-body", display: "swap"});
const heading = Space_Grotesk({subsets: ["latin"], variable: "--font-heading", display: "swap"});

export const metadata = {title: "Project Opportunities from TU Munich", description: "Find Project Studies, Informatics IDPs and other projects across audited TUM sources."};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en" className={`${body.variable} ${heading.variable}`}><body><CatalogProvider>{children}</CatalogProvider><AnalyticsConsent/><ContactPill/></body></html>;
}
