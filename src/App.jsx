import SearchSection from './SearchSection.jsx'
import DealsSection from './DealsSection.jsx'
import useSmoothWheelScroll from './useSmoothWheelScroll.js'
import Navbar from './Navbar.jsx'

function App() {
  useSmoothWheelScroll()

  return (
    <main className="relative isolate overflow-hidden bg-gradient-to-b from-[#102746] via-[#0c203c] to-[#102746] text-white">
        <Navbar />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_12%,_rgba(37,99,180,0.24),_transparent_52%)]" aria-hidden="true" />
        <div className="animate-aurora pointer-events-none absolute -inset-[20%] bg-[radial-gradient(ellipse_at_30%_35%,_rgba(37,99,180,0.3),_transparent_42%),radial-gradient(ellipse_at_75%_65%,_rgba(56,130,220,0.2),_transparent_40%)] bg-[length:160%_160%] motion-reduce:animate-none" aria-hidden="true" />
        <div className="animate-drift pointer-events-none absolute -left-40 top-[28rem] size-[28rem] rounded-full bg-blue-500/15 blur-3xl motion-reduce:animate-none" aria-hidden="true" />
        <div className="animate-drift pointer-events-none absolute -right-48 top-[54rem] size-[38rem] rounded-full bg-sky-400/15 blur-3xl [animation-delay:-4s] motion-reduce:animate-none" aria-hidden="true" />
        <section id="home" className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-24 text-center">
          <div className="flex flex-col items-center">
            <p className="animate-fade-in mb-5 text-xs font-semibold uppercase tracking-[0.4em] text-blue-200/75">Shop smarter</p>
            <h1 className="animate-fade-up text-7xl font-semibold leading-none tracking-tight sm:text-8xl md:text-9xl">Shoppie</h1>
            <div className="anim-line-grow mt-8 h-px w-20 bg-blue-300/70 [animation-delay:180ms] motion-reduce:animate-none" />
          </div>
        </section>
        <SearchSection />
        <DealsSection />
    </main>
  )
}

export default App
