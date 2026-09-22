import { Route, Routes } from 'react-router'
import HomePage from './components/HomePage'
import PrivacyPolicy from './components/PrivacyPolicy'
import RegistrationForm from './components/RegistrationForm'
import NotFoundPage from './pages/NotFoundPage'
import TestEditorPage from './pages/TestEditorPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/register" element={<main className="registration-page"><RegistrationForm /></main>} />
      <Route path="/tests/:testId/edit" element={<TestEditorPage />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
