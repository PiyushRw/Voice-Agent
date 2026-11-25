export async function api(path, body) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch('/api' + path, {
    headers,
    ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) })
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : 'The request could not be completed.')
  }
  return response.json()
}
