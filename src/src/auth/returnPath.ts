export function safeReturnPath(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/^\/(login|register)(\/|\?|#|$)/.test(value) ? value : '/'
}
