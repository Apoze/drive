import { baseApiUrl } from '@/features/api/utils';

/** End suite sessions before invoking the application's native OIDC logout. */
export async function logoutFromSuite(): Promise<boolean> {
  const endpoint = new URL('suite/logout/', baseApiUrl());
  const cookieName = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME || 'csrftoken';
  const csrf = () => document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(cookieName + '='))?.slice(cookieName.length + 1);
  try {
    if (!csrf()) await fetch(endpoint, { credentials: 'include' });
    const response = await fetch(endpoint, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() || '' },
      body: '{}',
    });
    if (!response.ok) throw new Error('Logout unavailable');
    const result = await response.json() as { redirect_url: string; suite_revoked?: boolean; provider_logout_available?: boolean };
    const redirect = new URL(result.redirect_url);
    if (redirect.origin !== endpoint.origin) throw new Error('Invalid logout destination');
    if (result.suite_revoked && result.provider_logout_available === false) {
      window.alert('Vos sessions de la suite sont révoquées. Votre fournisseur ne propose pas de déconnexion commune : sa session peut rester ouverte.');
    }
    window.location.replace(redirect.href);
    return true;
  } catch {
    window.alert('La déconnexion de la suite n’a pas pu être confirmée. Réessayez.');
    return false;
  }
}
