import { apiFetch, LOCAL_MODE, session } from '../api/client'
import { useAuth } from '../auth/useAuth'
import StartAttempt from '../practice/StartAttempt'
import OpenAttempts from '../practice/OpenAttempts'
import { Link, useNavigate } from 'react-router'
import { useEffect, useRef, useState } from 'react'
type Quiz = { id: number; title: string; description: string; created_at: string }

function HomePage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const [tests, setTests] = useState<Quiz[]>([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('newest')
  const [sortOpen, setSortOpen] = useState(false)
  const sortMenuRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [revision, setRevision] = useState(0)

  async function deleteTest(test: Quiz) {
    if (!window.confirm(`Удалить тест «${test.title}»? Старые результаты прохождения сохранятся.`)) return
    setError('')
    try {
      const response = await apiFetch(`/tests/${test.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Не удалось удалить тест.')
      setRevision(value => value + 1)
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с хранилищем.') }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true)
      setError('')
      try {
        const all: Quiz[] = []
        for (let offset = 0; ; offset += 100) {
          const response = await apiFetch(`/tests/?limit=100&offset=${offset}`, { signal: controller.signal })
          if (!response.ok) throw new Error(response.status === 401 ? 'Сессия истекла. Войдите ещё раз.' : 'Не удалось загрузить тесты.')
          const page: Quiz[] = await response.json()
          all.push(...page)
          if (page.length < 100) break
        }
        setTests(all)
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Нет соединения с сервером.')
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void load()
    return () => controller.abort()
  }, [revision])

  useEffect(() => {
    if (!sortOpen) return
    function closeOutside(event: PointerEvent) {
      if (!sortMenuRef.current?.contains(event.target as Node)) setSortOpen(false)
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setSortOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [sortOpen])

  const filtered = tests.filter(test => test.title.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'title' ? a.title.localeCompare(b.title, 'ru') : sort === 'oldest' ? a.id - b.id : b.id - a.id)

  return <div className="home">
    <header className="home-header"><Link className="home-logo" to="/">quiz<span>.</span></Link><nav className="home-nav" aria-label="Разделы"><Link to="/history">История</Link><Link to="/favorites">Избранное</Link></nav>{LOCAL_MODE ? <Link className="account-button" to="/login">Войти ↗</Link> : <button className="account-button" disabled={loggingOut} title={user?.email} onClick={async () => { setLoggingOut(true); setError(''); try { await session.logout() } catch { setError('Не удалось выйти. Проверьте соединение и повторите попытку.') } finally { setLoggingOut(false) } }}>{loggingOut ? 'Выходим…' : 'Выйти'}<span aria-hidden="true">↗</span></button>}</header>
    <main className="home-content">
      <OpenAttempts />
      <div className="home-heading"><div><p className="home-kicker">БИБЛИОТЕКА</p><h1>Мои тесты<span>{tests.length.toString().padStart(2, '0')}</span></h1></div><div className="home-actions"><button className="primary-action" onClick={() => navigate('/tests/new')}><span aria-hidden="true">+</span> Создать тест</button></div></div>
      <div className="home-toolbar"><div className="home-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></svg><input aria-label="Поиск тестов" placeholder="Найти тест" value={query} onChange={e => setQuery(e.target.value)} /></div><div className="sort-menu" ref={sortMenuRef}><button className={`sort-trigger${sortOpen ? ' is-open' : ''}`} type="button" aria-haspopup="menu" aria-expanded={sortOpen} onClick={() => setSortOpen(value => !value)}><span className="sort-caption">Сортировка</span><span className="sort-current">{sort === 'newest' ? 'Сначала новые' : sort === 'oldest' ? 'Сначала старые' : 'По названию'}</span><svg className="sort-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg></button>{sortOpen && <div className="sort-options" role="menu" aria-label="Сортировать тесты">{[{ value: 'newest', label: 'Сначала новые' }, { value: 'oldest', label: 'Сначала старые' }, { value: 'title', label: 'По названию' }].map(option => <button key={option.value} type="button" role="menuitemradio" aria-checked={sort === option.value} className={sort === option.value ? 'selected' : ''} onClick={() => { setSort(option.value); setSortOpen(false) }}>{option.label}{sort === option.value && <span aria-hidden="true">✓</span>}</button>)}</div>}</div></div>
      {error && <div className="error" role="alert">{error} <button onClick={() => setRevision(v => v + 1)}>Повторить</button></div>}
      {loading ? <div className="home-empty" role="status">Загружаем тесты…</div> : filtered.length ? <div className="quiz-grid">{filtered.map(test => <article className="quiz-card" key={test.id}><div className="quiz-card-top"><span className="quiz-mark" aria-hidden="true">≡</span><span>{new Date(test.created_at).toLocaleDateString('ru-RU')}</span></div><h2><Link to={`/tests/${test.id}/edit`}>{test.title}</Link></h2><p>{test.description || 'Без описания'}</p><StartAttempt testId={test.id} /><Link className="quiz-edit" to={`/tests/${test.id}/edit`}>Редактировать</Link><button className="quiz-delete" onClick={() => void deleteTest(test)}>Удалить тест</button><span className="quiz-private">Личный тест</span></article>)}</div> : <section className="home-empty"><div className="empty-drawing" aria-hidden="true"><div className="paper-back" /><div className="paper-front"><span /><span /><i>✓</i></div></div><h2>{query ? 'Ничего не нашлось' : 'Здесь будут твои тесты'}</h2><p>{query ? 'Попробуй другое название.' : 'Создай первый тест.'}</p><button className="empty-link" onClick={() => query ? setQuery('') : navigate('/tests/new')}>{query ? 'Сбросить поиск' : 'Создать первый тест'} <span aria-hidden="true">→</span></button></section>}
      <div className="home-bottom"><span><span aria-hidden="true">▣</span> Видно только тебе</span><span>PDF, HTML и JSON · до 8 МБ</span></div>
    </main>
    <footer className="home-footer"><span>quiz.</span><Link to="/privacy">Обработка персональных данных</Link></footer>
  </div>
}
export default HomePage
