import SearchSection from './SearchSection.jsx'

function App() {
  return (
    <>
      <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-800/50 via-navy to-[#071326]" aria-hidden="true" />
        <div className="absolute -left-40 top-1/4 size-96 rounded-full bg-blue-500/10 blur-3xl" aria-hidden="true" />
        <div className="absolute -bottom-48 -right-24 size-[34rem] rounded-full bg-sky-400/10 blur-3xl" aria-hidden="true" />
        <section className="relative z-10 px-6 py-24 text-center">
          <p className="animate-fade-in mb-5 text-xs font-semibold uppercase tracking-[0.4em] text-blue-200/75">Shop smarter</p>
          <h1 className="animate-fade-up text-7xl font-semibold tracking-tight sm:text-8xl md:text-9xl">Shoppie</h1>
          <div className="animate-fade-in mx-auto mt-8 h-px w-20 bg-blue-300/70 [animation-delay:180ms]" />
        </section>
      </main>
      <SearchSection />
    </>
  )
}

export default App
