import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiProxy = {
  '/api/v1': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react()],
  build: { manifest: true, sourcemap: false },
  server: { proxy: apiProxy },
  preview: { proxy: apiProxy },
})
