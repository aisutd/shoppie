import { useEffect, useRef, useState } from 'react'
import SearchSection from './SearchSection.jsx'
import SearchResults from './SearchResults.jsx'
import DealsSection from './DealsSection.jsx'
import Navbar from './Navbar.jsx'
import Icon from './Icon.jsx'
import PageBackLink from './PageBackLink.jsx'

const searchStorageKey = 'shoppie.search'

function currentRoute() {
  return window.location.pathname.replace(/\/$/, '') === '/discover' ? '/discover' : '/'
}

function replaceLegacyRoute() {
  // keep the saved search on Home and replace the obsolete history entry
  if (/^\/listings\/?$/.test(window.location.pathname)) window.history.replaceState(null, '', '/')
}

function scrollTo(element) {
  if (!element) return
  element.focus({ preventScroll: true })
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  element.scrollIntoView({ behavior: reducedMotion ? 'instant' : 'smooth', block: 'start' })
}

function savedSearch() {
  try {
    const search = JSON.parse(window.sessionStorage.getItem(searchStorageKey))
    return typeof search?.query === 'string' && Array.isArray(search.products) ? search : null
  } catch {
    return null
  }
}

function Home({ onResults, navigate, isActive }) {
  const lighting = useRef(null)

  useEffect(() => {
    if (!isActive) return
    const motion = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)')
    let frame = 0
    function follow(event) {
      if (!motion.matches || event.pointerType !== 'mouse') return
      cancelAnimationFrame(frame)
      const x = (event.clientX / window.innerWidth - 0.5) * 38
      const y = (event.clientY / window.innerHeight - 0.5) * 28
      frame = requestAnimationFrame(() => {
        lighting.current?.style.setProperty('--light-x', `${x}px`)
        lighting.current?.style.setProperty('--light-y', `${y}px`)
      })
    }
    function reset() {
      cancelAnimationFrame(frame)
      lighting.current?.style.removeProperty('--light-x')
      lighting.current?.style.removeProperty('--light-y')
    }
    window.addEventListener('pointermove', follow, { passive: true })
    document.documentElement.addEventListener('pointerleave', reset)
    motion.addEventListener('change', reset)
    return () => {
      window.removeEventListener('pointermove', follow)
      document.documentElement.removeEventListener('pointerleave', reset)
      motion.removeEventListener('change', reset)
      reset()
    }
  }, [isActive])

  return (
    <section className="home-page">
      <div className="home-lighting" ref={lighting} aria-hidden="true">
        <div className="home-arc home-arc-left" />
        <div className="home-arc home-arc-right" />
        <div className="home-arc home-arc-low" />
      </div>
      <div className="home-content page-enter">
        <h1 aria-label="Shop smarter, not harder.">Shop <span className="hero-accent">smarter</span>,<br className="hero-break" /> not harder.</h1>
        <p>Find and compare the best deals on tech products like laptops, monitors, headphones, and more.</p>
        <SearchSection onResults={onResults} />
        <div className="home-discover">
          <span><Icon name="tag" /> Compare prices across retailers</span>
          <a href="/discover" onClick={event => navigate('/discover', event)}>
            Browse tech deals <Icon name="arrow" />
          </a>
        </div>
      </div>
    </section>
  )
}

function App() {
  const [route, setRoute] = useState(currentRoute)
  const [searchResults, setSearchResults] = useState(savedSearch)
  const [hasVisitedDiscover, setHasVisitedDiscover] = useState(route === '/discover')
  const searchVersion = useRef(0)
  const main = useRef(null)
  const resultsArea = useRef(null)
  const revealResults = useRef(false)
  const focusOnRoute = useRef(false)
  const currentSearchVersion = searchVersion.current

  function showRoute(path) {
    if (path === '/discover') setHasVisitedDiscover(true)
    focusOnRoute.current = true
    setRoute(path)
  }

  function navigate(path, event) {
    // keep normal link behavior for new tabs and modified clicks
    if (event && (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)) return
    event?.preventDefault()
    if (window.location.pathname === path) return
    window.history.pushState(null, '', path)
    showRoute(path)
  }

  function saveResults(results) {
    revealResults.current = currentRoute() === '/'
    setSearchResults(results)
    try {
      window.sessionStorage.setItem(searchStorageKey, JSON.stringify(results))
    } catch {
      // results stay available in app state when session storage is unavailable
    }
  }

  function showResults(results) {
    searchVersion.current += 1
    saveResults(results)
  }

  function refineResults(results) {
    // an older refinement may finish after a new Home search
    if (currentSearchVersion === searchVersion.current) saveResults(results)
  }

  useEffect(() => {
    replaceLegacyRoute()
    const goBackOrForward = () => {
      replaceLegacyRoute()
      showRoute(currentRoute())
    }
    window.addEventListener('popstate', goBackOrForward)
    return () => window.removeEventListener('popstate', goBackOrForward)
  }, [])

  useEffect(() => {
    document.title = route === '/' ? 'Shoppie | Shop smarter' : 'Discover | Shoppie'
    if (!focusOnRoute.current) return
    focusOnRoute.current = false
    window.scrollTo(0, 0)
    main.current?.focus({ preventScroll: true })
  }, [route])

  useEffect(() => {
    if (route === '/' && revealResults.current) {
      revealResults.current = false
      scrollTo(resultsArea.current?.querySelector('h2'))
    }
  }, [route, searchResults])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Navbar route={route} navigate={navigate} />
      <main id="main-content" ref={main} tabIndex={-1}>
        <div hidden={route !== '/'} className={searchResults ? 'home-with-results' : undefined}>
          <Home onResults={showResults} navigate={navigate} isActive={route === '/'} />
          {searchResults && (
            <div ref={resultsArea}>
              <SearchResults key={currentSearchVersion} search={searchResults} isActive={route === '/'}
                onNewSearch={() => scrollTo(main.current?.querySelector('#product-search'))} onRefined={refineResults} />
            </div>
          )}
        </div>
        {hasVisitedDiscover && (
          <div hidden={route !== '/discover'}>
            <DealsSection isActive={route === '/discover'} footer={<PageBackLink to="/" navigate={navigate} />} />
          </div>
        )}
      </main>
    </div>
  )
}

export default App
