const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]'])

export function isAllowedRuntimeUrl(input: string | URL, base = window.location.href): boolean {
  const url = new URL(input, base)
  if (url.protocol === 'data:' || url.protocol === 'blob:') return true
  return (url.protocol === 'http:' || url.protocol === 'https:' || url.protocol === 'ws:' || url.protocol === 'wss:') && LOCAL_HOSTS.has(url.hostname.toLowerCase())
}

export function installNetworkTripwire(): void {
  if (typeof window === 'undefined' || window.datasetNetworkTripwire === 'installed') return
  window.datasetNetworkTripwire = 'installed'

  if (window.fetch) {
    const nativeFetch = window.fetch.bind(window)
    window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input
      if (!isAllowedRuntimeUrl(url)) throw new Error(`External request blocked: ${new URL(url, window.location.href).origin}`)
      return nativeFetch(input, init)
    }) as typeof window.fetch
  }

  const nativeOpen = XMLHttpRequest.prototype.open
  XMLHttpRequest.prototype.open = function (method: string, url: string | URL, async: boolean = true, username?: string | null, password?: string | null) {
    if (!isAllowedRuntimeUrl(url)) throw new Error(`External request blocked: ${new URL(url, window.location.href).origin}`)
    const open = nativeOpen as (this: XMLHttpRequest, method: string, url: string, async?: boolean, username?: string | null, password?: string | null) => void
    return open.call(this, method, String(url), async, username, password)
  }

  const NativeWebSocket = window.WebSocket
  window.WebSocket = class LocalOnlyWebSocket extends NativeWebSocket {
    constructor(url: string | URL, protocols?: string | string[]) {
      if (!isAllowedRuntimeUrl(url)) throw new Error(`External request blocked: ${new URL(url, window.location.href).origin}`)
      super(url, protocols)
    }
  }

  const sendBeacon = navigator.sendBeacon?.bind(navigator)
  if (sendBeacon) {
    Object.defineProperty(navigator, 'sendBeacon', {
      configurable: true,
      value: (url: string | URL, data?: BodyInit | null) => {
        if (!isAllowedRuntimeUrl(url)) throw new Error(`External request blocked: ${new URL(url, window.location.href).origin}`)
        return sendBeacon(String(url), data)
      },
    })
  }
}

declare global {
  interface Window {
    datasetNetworkTripwire?: 'installed'
  }
}
