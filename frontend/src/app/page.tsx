import { CloneInterface } from '@/components/features/CloneInterface';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

export default function Home() {
  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gray-50">
        <CloneInterface />
      </div>
    </ErrorBoundary>
  );
}