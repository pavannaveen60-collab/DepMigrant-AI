import { RepositoriesPage } from '@/components/pages/RepositoriesPage';

export default function RepositoriesRoute({ searchParams }: { searchParams: { query?: string } }) {
  return <RepositoriesPage initialQuery={searchParams.query ?? ''} />;
}
