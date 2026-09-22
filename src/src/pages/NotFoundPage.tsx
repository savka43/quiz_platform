import { Link } from 'react-router'

function NotFoundPage() {
  return (
    <main className="registration-page">
      <section className="form-panel">
        <h1>Страница не найдена</h1>
        <Link className="policy-back" to="/">← На главную</Link>
      </section>
    </main>
  )
}

export default NotFoundPage
