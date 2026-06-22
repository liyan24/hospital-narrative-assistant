import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

const FRONTEND_PORT = Number(process.env.VITE_FRONTEND_PORT) || 8501
const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8005'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: FRONTEND_PORT,
    proxy: {
      '/api': {
        target: API_BASE_URL,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
