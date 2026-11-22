import { defineConfig } from 'vite';

// During development, forward backend requests to the FastAPI server, so the browser never talks to it directly.
// Default: the backend on this computer. To use a backend on another computer, start the page with
//   BACKEND_URL=http://<ip-address>:8001 npm run dev
const target = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  server: {
    proxy: {
      '/design': target,
      '/health': target,
      '/image': target,
    },
  },
});
