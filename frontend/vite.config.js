import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/',
  build: {
    outDir: 'dist',
    assetsDir: 'static',
    rollupOptions: {
      // Две страницы: CRM (index.html) и витрина магазина (shop.html) — разные бандлы,
      // покупатель не скачивает код CRM.
      input: {
        index: 'index.html',
        shop: 'shop.html',
      },
      output: {
        entryFileNames: 'static/[name].js',
        // Общий код двух страниц (React) — отдельный чанк. Имя с хешем: точки входа сбрасывают
        // кэш меткой ?v= в шаблоне, а чанк подгружается по имени, и старый из кэша сломал бы новый бандл.
        chunkFileNames: 'static/[name]-[hash].js',
        assetFileNames: 'static/[name].[ext]'
      }
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
