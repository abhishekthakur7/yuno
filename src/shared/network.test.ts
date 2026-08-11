import { isAllowedRuntimeUrl } from './network'

describe('runtime network tripwire', () => {
  it('allows only local runtime traffic and inert document URLs', () => {
    expect(isAllowedRuntimeUrl('/src/main.tsx', 'http://127.0.0.1:5173/')).toBe(true)
    expect(isAllowedRuntimeUrl('ws://localhost:5173/', 'http://localhost:5173/')).toBe(true)
    expect(isAllowedRuntimeUrl('data:text/plain,fixture', 'http://localhost/')).toBe(true)
    expect(isAllowedRuntimeUrl('https://example.com/collect', 'http://localhost/')).toBe(false)
    expect(isAllowedRuntimeUrl('wss://telemetry.example.com', 'http://localhost/')).toBe(false)
  })
})
