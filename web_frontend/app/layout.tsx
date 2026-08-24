import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SwarmOS Simulation Control Center',
  description: 'Real-time control and visualization for multi-robot warehouse simulation',
  viewport: 'width=device-width, initial-scale=1',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-darker text-gray-100">
        {children}
      </body>
    </html>
  )
}
