import "./globals.css";
import {ClerkProvider} from "@clerk/nextjs";
export const metadata={title:"TUM Project Studies Portal",description:"Find active Project Studies across TUM School of Management chairs."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><ClerkProvider>{children}</ClerkProvider></body></html>}
