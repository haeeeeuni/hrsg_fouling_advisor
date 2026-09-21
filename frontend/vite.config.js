import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 개발 중 /api 는 Django 로 넘긴다 (specs/16 §10)
    proxy: {
      '/api': {
        // localhost 는 환경에 따라 ::1(IPv6) 로 먼저 풀리는데 runserver 는
        // 기본적으로 127.0.0.1 에만 바인딩한다. IPv4 를 직접 가리킨다.
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.js'],
    // Node 26 의 실험적 localStorage 전역이 jsdom 구현을 가리는 문제를 보정한다.
    setupFiles: ['./tests/setup.js'],
  },
})
