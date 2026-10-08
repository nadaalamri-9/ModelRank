import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      // The links page is served at /links/
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        links: resolve(import.meta.dirname, 'links/index.html'),
      },
    },
  },
})
