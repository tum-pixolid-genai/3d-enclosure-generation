import { defineConfig } from 'vite';

// During development, forward backend requests to the FastAPI server, so the browser never talks to it directly.
export default defineConfig({
  server: {
    proxy: {
      '/design': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
});
