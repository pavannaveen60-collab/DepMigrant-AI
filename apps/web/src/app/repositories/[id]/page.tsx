import { RepositoryDetailsPage } from '@/components/pages/RepositoryDetailsPage';

export default function RepositoryDetailsRoute({ params }: { params: { id: string } }) {
  return <RepositoryDetailsPage repositoryId={params.id} />;
}
