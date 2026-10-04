import { expect, it } from 'vitest'
import { safeReturnPath } from './returnPath'

it('returns to an internal route and prevents external redirects or login loops', () => {
  expect(safeReturnPath('/tests/12/edit?tab=questions')).toBe('/tests/12/edit?tab=questions')
  for (const value of [undefined, 'https://evil.example', '//evil.example', '/\\evil.example', '/login', '/register?x=1']) expect(safeReturnPath(value)).toBe('/')
})
