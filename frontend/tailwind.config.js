/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // Habilita el cambio manual de tema mediante clase
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        graphito: {
          dark: '#0f172a',       // Fondo principal en Modo Oscuro (Slate-900)
          card: '#1e293b',       // Tarjetas en Modo Oscuro
          border: '#334155',     // Bordes en Modo Oscuro
          blue: '#3b82f6',       // Azul primario
          violet: '#a78bfa',     // Violeta del gradiente
        },
        risk: {
          high: '#ef4444',       
          medium: '#f59e0b',     
          low: '#3b82f6',        
        }
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'sans-serif'], 
        body: ['Inter', 'sans-serif'],                  
      },
      backgroundImage: {
        'button-grad': 'linear-gradient(to bottom, #3b82f6, #a78bfa)',
      }
    },
  },
  plugins: [],
}