import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxy = {
  '/api': 'http://localhost:8000',
  '/health': 'http://localhost:8000',
}

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy,
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
    proxy,
  },
})
