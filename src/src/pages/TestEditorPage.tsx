import { Link, useParams } from 'react-router'
import NotFoundPage from './NotFoundPage'

function TestEditorPage() {
  const { testId } = useParams<{ testId: string }>()

  if (!testId || !/^[1-9]\d*$/.test(testId)) return <NotFoundPage />

  return (
    <main className="policy-page">
      <Link className="policy-back" to="/">← Мои тесты</Link>
      <section className="policy-document">
        <h1>Редактирование теста</h1>
        <p>Тест № {testId}</p>
        <p>Редактор пока не подключён.</p>
      </section>
    </main>
  )
}

export default TestEditorPage
