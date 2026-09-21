import HomePage from './components/HomePage'
import PrivacyPolicy from './components/PrivacyPolicy'
import RegistrationForm from './components/RegistrationForm'

function App() {
  if (window.location.pathname.replace(/\/$/, '') === '/privacy') return <PrivacyPolicy />
  if (window.location.pathname.replace(/\/$/, '') === '/register') return <main className="registration-page"><RegistrationForm /></main>
  return <HomePage />
}

export default App
