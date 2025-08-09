import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import * as path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(process.cwd(), './src'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api/upload': {
        target: 'http://localhost:8901',
        changeOrigin: true,
        rewrite: (pathStr) => pathStr.replace(/^\/api\/upload/, '/upload')
      },
      '/api/config': {
        target: 'http://localhost:8911',
        changeOrigin: true,
        rewrite: (pathStr) => pathStr.replace(/^\/api\/config/, '')
      },
      '/api': {
        target: 'http://localhost:8900',
        changeOrigin: true
      }
    }
  }
})