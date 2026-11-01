import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ThemeProvider } from './context/ThemeContext'
import { TourProvider } from './components/tour/TourProvider'

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <ThemeProvider>
            <TourProvider>
                <App />
            </TourProvider>
        </ThemeProvider>
    </StrictMode>,
)

