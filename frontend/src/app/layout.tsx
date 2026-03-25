import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "SAP O2C Graph Intelligence",
  description: "Graph-Based Data Modeling and Conversational Query System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`} style={{height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        <header className="glass" style={{
          height: '60px', 
          display: 'flex', 
          alignItems: 'center', 
          padding: '0 1.5rem',
          borderBottom: '1px solid var(--border)',
          zIndex: 10
        }}>
          <div style={{display: 'flex', alignItems: 'center', gap: '0.75rem'}}>
            <div style={{
              width: '28px', height: '28px', 
              background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
              borderRadius: '6px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'white', fontWeight: 'bold', fontSize: '14px'
            }}>G</div>
            <h1 style={{fontSize: '1.1rem', fontWeight: 600, letterSpacing: '-0.01em'}}>
              SAP Graph Intelligence
            </h1>
            <span style={{
              marginLeft: '0.5rem',
              fontSize: '0.75rem',
              padding: '0.15rem 0.5rem',
              background: 'rgba(59, 130, 246, 0.1)',
              color: 'var(--primary)',
              borderRadius: '999px',
              fontWeight: 500
            }}>Order to Cash</span>
          </div>
        </header>
        <main style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
          {children}
        </main>
      </body>
    </html>
  );
}
