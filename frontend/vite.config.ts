import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/ui/', plugins: [react()],
  server: {proxy: {'/api': {target: 'http://127.0.0.1:8080', changeOrigin: false}}},
  test: {environment: 'jsdom', restoreMocks: true}
});
