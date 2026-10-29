import { useEffect, useState } from 'react'

const links = [
  { label: 'Home', href: '#home' },
  { label: 'Search products', href: '#search' },
  { label: 'Discover deals', href: '#deals' },
]

function Navbar() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 32)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!open) return undefined

    const previousOverflow = document.body.style.overflow
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const closeMenu = () => setOpen(false)
  const navigateToSection = () => {
    window.cancelSmoothScroll?.()
    closeMenu()
  }
  const openMenu = () => {
    window.cancelSmoothScroll?.()
    setOpen(true)
  }

  return (
    <>
      <header className={`fixed inset-x-0 top-0 z-40 border-b transition-colors duration-300 ${scrolled ? 'border-blue-100/10 bg-[#091a30]/90 shadow-lg shadow-black/10 backdrop-blur-xl' : 'border-transparent bg-transparent'}`}>
        <div className="mx-auto flex h-[4.5rem] max-w-7xl items-center justify-between px-6 sm:px-10">
          <a href="#home" onClick={navigateToSection} className="flex items-center gap-2.5 rounded-lg text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300" aria-label="Shoppie home">
            <span className="grid size-9 place-items-center rounded-xl bg-blue-500 text-lg font-bold shadow-lg shadow-blue-950/30">s</span>
            <span className="text-lg font-semibold tracking-tight">Shoppie</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="#home" onClick={navigateToSection} className="rounded-lg px-3 py-2 text-sm font-medium text-blue-100/80 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">Home</a>
            <button
              type="button"
              onClick={openMenu}
              aria-label="Open navigation menu"
              aria-expanded={open}
              aria-controls="site-navigation"
              className="group grid size-11 place-items-center rounded-xl border border-blue-100/15 bg-[#0b1d35]/70 text-blue-50 transition hover:border-blue-200/30 hover:bg-blue-900/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
            >
              <span className="flex flex-col gap-[5px]" aria-hidden="false">
                <span className="h-0.5 w-5 rounded-full bg-current transition group-hover:w-6" />
                <span className="h-0.5 w-6 rounded-full bg-current" />
                <span className="h-0.5 w-4 rounded-full bg-current transition group-hover:w-6" />
              </span>
            </button>
          </div>
        </div>
      </header>

      <div
        data-scroll-lock
        onClick={closeMenu}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-[#030b16]/75 backdrop-blur-sm transition-opacity duration-300 ${open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'}`}
      />

      <nav
        id="site-navigation"
        data-scroll-lock
        aria-label="Main navigation"
        aria-hidden={!open}
        className={`fixed inset-y-0 right-0 z-50 flex w-[min(21rem,88vw)] flex-col border-l border-blue-100/10 bg-gradient-to-b from-[#102746] to-[#071326] shadow-2xl shadow-black/40 transition-transform duration-500 ease-[cubic-bezier(0.76,0,0.24,1)] ${open ? 'translate-x-0 visible' : 'translate-x-full invisible'}`}
      >
        <div className="flex items-center justify-between border-b border-blue-100/10 px-7 py-6">
          <span className="text-xs font-semibold uppercase tracking-[0.3em] text-blue-200/60">Menu</span>
          <button type="button" onClick={closeMenu} className="rounded-lg px-3 py-2 text-sm font-medium text-blue-100/75 transition hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">Close</button>
        </div>
        <div className="flex flex-1 flex-col px-7 pt-5">
          {links.map((link, index) => (
            <a
              key={link.href}
              href={link.href}
              onClick={navigateToSection}
              tabIndex={open ? 0 : -1}
              className="group flex items-center justify-between border-b border-blue-100/10 py-5 text-xl font-medium text-white transition-colors hover:text-blue-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
              style={{ transitionDelay: open ? `${index * 45}ms` : '0ms' }}
            >
              {link.label}
              <span aria-hidden="true" className="translate-x-0 text-blue-300 opacity-0 transition duration-300 group-hover:translate-x-1 group-hover:opacity-100">→</span>
            </a>
          ))}
        </div>
        <p className="px-7 py-6 text-xs tracking-wide text-blue-100/35">© {new Date().getFullYear()} Shoppie</p>
      </nav>
    </>
  )
}

export default Navbar
