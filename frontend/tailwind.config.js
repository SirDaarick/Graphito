/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        graphito: {
          dark: '#0f172a',       // Fondo principal (Slate-900)
          card: '#1e293b',       // Fondo de las tarjetas
          border: '#334155',     // Bordes sutiles
          blue: '#3b82f6',       // Azul primario
          violet: '#a78bfa',     // Violeta del gradiente
        },
        risk: {
          high: '#ef4444',       // Rojo (89% Similitud)
          medium: '#f59e0b',     // Ámbar (42% Similitud)
          low: '#3b82f6',        // Azul/Indigo (12% Similitud)
        }
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'sans-serif'], // Títulos
        body: ['Inter', 'sans-serif'],                  // Contenido
      },
      backgroundImage: {
        'button-grad': 'linear-gradient(to bottom, #3b82f6, #a78bfa)',
      }
    },
  },
  plugins: [],
}