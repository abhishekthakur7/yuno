import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppRouter } from './app/router'

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')

createRoot(root).render(<StrictMode><AppRouter /></StrictMode>)
