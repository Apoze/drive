import { baseApiUrl } from '../api/utils'
import { mobileIntakeMetadata } from '../sdk/mobileIntake'

export const authUrl = ({
  silent = false,
  returnTo = window.location.href,
} = {}) => {
  const destination = new URL(returnTo, window.location.origin)
  if (destination.origin === window.location.origin && destination.pathname === '/sdk/chat' &&
      destination.searchParams.get('intake') === '1' && destination.hash.startsWith('#apoze-intake=')) {
    mobileIntakeMetadata(destination.searchParams.get('request') || '')
    destination.hash = ''
    returnTo = destination.href
  }
  return new URL(
    `authenticate/?silent=${encodeURIComponent(silent)}&returnTo=${encodeURIComponent(returnTo)}`,
    baseApiUrl()
  )
}
