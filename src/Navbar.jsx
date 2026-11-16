const links = [
  { label: 'Home', href: '/' },
  { label: 'Discover', href: '/discover' },
]

function Navbar({ route, navigate }) {
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <a href="/" onClick={event => navigate('/', event)} className="site-logo" aria-label="Shoppie home">
          <img src="/branding/shoppie-logo-primary-dark-bg.svg" alt="Shoppie" width="203" height="56" />
        </a>
        <nav aria-label="Main navigation" className="site-nav">
          {links.map(({ label, href }) => (
            <a key={href} href={href} onClick={event => navigate(href, event)}
              aria-current={route === href ? 'page' : undefined}>
              {label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  )
}

export default Navbar
