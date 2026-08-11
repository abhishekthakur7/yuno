import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppRouter } from './app/router'
import { installNetworkTripwire } from './shared/network'

installNetworkTripwire()

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')

createRoot(root).render(<StrictMode><AppRouter /></StrictMode>)
