import "./globals.css";
import {Inter, Space_Grotesk} from "next/font/google";

const body = Inter({subsets: ["latin"], variable: "--font-body", display: "swap"});
const heading = Space_Grotesk({subsets: ["latin"], variable: "--font-heading", display: "swap"});

export const metadata = {title: "Project Opportunities from TU Munich", description: "Find active Project Studies and Informatics IDPs across audited TUM sources."};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en" className={`${body.variable} ${heading.variable}`}><body>{children}</body></html>;
}
