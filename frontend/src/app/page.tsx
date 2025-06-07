import { CloneInterface } from '@/components/features/CloneInterface';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

export default function Home() {
  return (
    <ErrorBoundary>
      <CloneInterface />
    </ErrorBoundary>
  );
}