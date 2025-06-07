import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Website Cloner - AI-Powered Website Replication",
  description: "Clone any website using AI to create aesthetically similar HTML replicas",
  keywords: ["website cloner", "AI", "HTML", "web development", "design replication"],
  authors: [{ name: "Orchids Challenge" }],
  viewport: "width=device-width, initial-scale=1",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <ErrorBoundary>
          <div className="min-h-screen bg-white">
            {/* Header */}
            <header className="border-b border-gray-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-16">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                      <span className="text-white font-bold text-sm">WC</span>
                    </div>
                    <div>
                      <h1 className="text-xl font-semibold text-gray-900">Website Cloner</h1>
                      <p className="text-xs text-gray-500">AI-Powered Website Replication</p>
                    </div>
                  </div>
                  
                  <nav className="hidden md:flex items-center gap-6">
                    <a href="#how-it-works" className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                      How it works
                    </a>
                    <a href="#features" className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                      Features
                    </a>
                    <a href="#about" className="text-sm text-gray-600 hover:text-gray-900 transition-colors">
                      About
                    </a>
                  </nav>
                </div>
              </div>
            </header>

            {/* Main Content */}
            <main className="flex-1">
              {children}
            </main>

            {/* Footer */}
            <footer className="border-t border-gray-200 bg-gray-50">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-3">Website Cloner</h3>
                    <p className="text-sm text-gray-600">
                      Create aesthetically similar website replicas using advanced AI technology.
                    </p>
                  </div>
                  
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Features</h4>
                    <ul className="space-y-2 text-sm text-gray-600">
                      <li>AI-powered design analysis</li>
                      <li>Real-time progress tracking</li>
                      <li>Multiple quality options</li>
                      <li>Instant download</li>
                    </ul>
                  </div>
                  
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Support</h4>
                    <ul className="space-y-2 text-sm text-gray-600">
                      <li>Privacy-focused</li>
                      <li>No data retention</li>
                      <li>Secure processing</li>
                      <li>Open source</li>
                    </ul>
                  </div>
                </div>
                
                <div className="mt-8 pt-8 border-t border-gray-200 text-center">
                  <p className="text-sm text-gray-500">
                    © 2024 Website Cloner. Built for the Orchids Challenge.
                  </p>
                </div>
              </div>
            </footer>
          </div>
        </ErrorBoundary>
      </body>
    </html>
  );
}