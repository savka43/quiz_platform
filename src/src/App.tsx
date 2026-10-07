import { AuthBoundary, RequireAuth } from './auth/AuthBoundary'
import { GuestOnly } from './auth/AuthBoundary'
import { Route, Routes } from 'react-router'
import { LOCAL_MODE } from './api/client'
import LoginPage from './pages/LoginPage'
import RegistrationForm from './components/RegistrationForm'
import HomePage from './components/HomePage'
import PrivacyPolicy from './components/PrivacyPolicy'
import AccountRedirectPage from './pages/AccountRedirectPage'
import NotFoundPage from './pages/NotFoundPage'
import TestEditorPage from './pages/TestEditorPage'
import AttemptPage from './pages/AttemptPage'
import AttemptResultPage from './pages/AttemptResultPage'
import HistoryPage from './pages/HistoryPage'
import FavoritesPage from './pages/FavoritesPage'

function App() {
  return (
    <Routes>
      <Route element={<AuthBoundary />}>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/tests/new" element={<TestEditorPage />} />
          <Route path="/tests/:testId/edit" element={<TestEditorPage />} />
          <Route path="/attempts/:attemptId" element={<AttemptPage />} />
          <Route path="/attempts/:attemptId/result" element={<AttemptResultPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/favorites" element={<FavoritesPage />} />
        </Route>
        <Route element={<GuestOnly />}>
          <Route path="/login" element={LOCAL_MODE ? <AccountRedirectPage page="login" /> : <LoginPage />} />
          <Route path="/register" element={LOCAL_MODE ? <AccountRedirectPage page="register" /> : <main className="registration-page"><RegistrationForm /></main>} />
        </Route>
      </Route>
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
