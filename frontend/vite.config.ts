import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Cargar variables de entorno según el modo (development, production, etc.)
  const env = loadEnv(mode, process.cwd(), '');
  
  // En Docker, las variables de entorno están en process.env
  // Vite's loadEnv solo carga desde archivos .env por defecto
  const proxyTarget = env.VITE_PROXY_TARGET || process.env.VITE_PROXY_TARGET || 'http://localhost:8000';
  
  console.log(`[Vite Config] Mode: ${mode}`);
  console.log(`[Vite Config] Proxy target: ${proxyTarget}`);

  return {
    plugins: [react()],
    server: {
      host: true,
      allowedHosts: true,
      watch: {
        usePolling: true
      },
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, '/api'), // Asegurar que el prefijo se mantenga si es necesario
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('[Proxy Error]', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('[Proxy Request]', req.method, req.url, '->', proxyTarget + proxyReq.path);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('[Proxy Response]', proxyRes.statusCode, req.url);
            });
          }
        }
      }
    }
  }
})
