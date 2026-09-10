import { ReactNode, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { baseApiUrl } from '@/features/api/utils';

interface Catalogue {
  enabled: boolean;
  services: { id: string; app_id: string; name: string; url: string; allowed: boolean; available: boolean; reason: string }[];
}

export const SuiteCatalogue = ({ fallback = null }: { fallback?: ReactNode }) => {
  const details = useRef<HTMLDetailsElement>(null);
  const query = useQuery<Catalogue>({
    queryKey: ['suite-catalogue'],
    queryFn: async () => {
      const response = await fetch(new URL('suite/catalogue/', baseApiUrl()), { credentials: 'include' });
      if (response.status === 404) return { enabled: false, services: [] };
      if (response.status === 401) return { enabled: true, services: [] };
      if (!response.ok) throw new Error('Catalogue indisponible');
      return response.json();
    },
    refetchInterval: 30000, staleTime: 20000, retry: false,
  });
  if (query.data?.enabled === false) return <>{fallback}</>;
  if (!query.isError && (!query.data || query.data.services.length === 0)) return null;
  return (
    <details ref={details} style={{ position: 'relative', marginInline: 8 }} onKeyDown={(event) => {
      if (event.key === 'Escape' && details.current) { details.current.open = false; details.current.querySelector('summary')?.focus(); }
    }}>
      <summary aria-label="Applications de la suite" style={{ cursor: 'pointer', padding: '8px 12px', borderRadius: 4 }}>Applications</summary>
      <nav aria-label="Applications de la suite" style={{ display: 'block', height: 'auto', minHeight: 0, boxSizing: 'border-box', position: 'absolute', insetInlineEnd: 0, top: '100%', width: 320, maxWidth: 'calc(100vw - 2rem)', padding: 16, background: 'var(--c--contextuals--background--surface--primary, #fff)', color: 'var(--c--contextuals--content--semantic--neutral--primary, #161616)', border: '1px solid #ddd', borderRadius: 8, boxShadow: '0 4px 16px #0002', zIndex: 1100 }}>
        {query.isError ? <div role="status">Catalogue indisponible. <button type="button" onClick={() => void query.refetch()}>Réessayer</button></div> :
          <ul style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, padding: 0, margin: 0, listStyle: 'none' }}>
            {query.data?.services.map((service) => <li key={service.id}>
              {service.allowed && service.available && /^https?:\/\//.test(service.url)
                ? <a href={service.url} aria-current={service.app_id === 'drive' ? 'page' : undefined} style={{ display: 'block', padding: 10, color: 'inherit', border: '1px solid #ddd', borderRadius: 4 }}>{service.name}</a>
                : <span aria-disabled="true" style={{ display: 'block', padding: 10 }}>{service.name}<small style={{ display: 'block' }}>{!service.available ? 'Indisponible' : service.reason === 'directory_unavailable' ? 'Vérification indisponible' : 'Accès non attribué'}</small></span>}
            </li>)}
          </ul>}
      </nav>
    </details>
  );
};
