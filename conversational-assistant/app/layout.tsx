import type { Metadata } from 'next'
import localFont from 'next/font/local'
import './globals.css'

const geistSans = localFont({
  src: './fonts/GeistVF.woff',
  variable: '--font-geist-sans',
  weight: '100 900'
})
const geistMono = localFont({
  src: './fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
  weight: '100 900'
})

export const metadata: Metadata = {
  title: 'Conversational Assistant',
  description: 'Structured Outputs demo',
  icons: {
    icon: '/imgs/convex_icon.svg'
  }
}

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} `}>
        <div className="flex h-screen w-full flex-col bg-background bg-legami text-stone-900 overflow-hidden">
          <main className="flex-1 flex flex-col min-h-0">{children}</main>
        </div>
      </body>
    </html>
  )
}
