import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8111'

  return {
    plugins: [vue()],
    server: {
      port: 3111,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
        '/uploads': { target: backendUrl, changeOrigin: true },
      },
    },
  }
})
