export function apiErrorMessage(error, fallback = 'The action could not be completed.') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map(item => typeof item === 'string' ? item : item?.msg || 'Invalid value').join('; ')
  }
  if (typeof detail === 'string') return detail
  return fallback
}
