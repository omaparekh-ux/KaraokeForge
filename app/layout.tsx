import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'KaraokeForge | Turn any song into karaoke',
  description: 'Create karaoke-ready videos with open-source audio processing.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}