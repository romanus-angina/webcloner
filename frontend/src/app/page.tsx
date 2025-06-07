'use client';

import { URLInput, type URLInputData } from '@/components/features/URLInput/URLInput';

export default function Home() {
  const handleSubmit = (data: URLInputData) => {
    console.log('Form submitted:', data);
  };

  return (
    <main className="min-h-screen p-8">
      <div className="container mx-auto">
        <URLInput onSubmit={handleSubmit} />
      </div>
    </main>
  );
}
