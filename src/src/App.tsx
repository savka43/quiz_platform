import { AuthBoundary, RequireAuth, GuestOnly } from './auth/AuthBoundary'
import LoginPage from './pages/LoginPage'
import { Route, Routes } from 'react-router'
import HomePage from './components/HomePage'
import PrivacyPolicy from './components/PrivacyPolicy'
import RegistrationForm from './components/RegistrationForm'
import NotFoundPage from './pages/NotFoundPage'
import TestEditorPage from './pages/TestEditorPage'
import AttemptPage from './pages/AttemptPage'

function App() {
  return (
    <Routes>
      <Route element={<AuthBoundary />}>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/tests/new" element={<TestEditorPage />} />
          <Route path="/tests/:testId/edit" element={<TestEditorPage />} />
          <Route path="/attempts/:attemptId" element={<AttemptPage />} />
        </Route>
        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<main className="registration-page"><RegistrationForm /></main>} />
        </Route>
      </Route>
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
