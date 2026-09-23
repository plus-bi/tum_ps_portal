import "./globals.css";
import {ClerkProvider} from "@clerk/nextjs";
export const metadata={title:"TUM Project Opportunities",description:"Find active Project Studies and Informatics IDPs across audited TUM sources."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><ClerkProvider>{children}</ClerkProvider></body></html>}
