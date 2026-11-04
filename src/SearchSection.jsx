import { useState } from 'react'

function SearchSection({ onResults }) {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch(event) {
    event.preventDefault()
    const searchQuery = query.trim()
    if (!searchQuery || isSearching) return

    setIsSearching(true)
    setError('')
    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Search failed. Please try again.')
      onResults({ query: searchQuery, products: data.products || [] })
    } catch (searchError) {
      setError(searchError.message || 'Could not reach local search. Start the local API and try again.')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section id="search" className="relative z-10 scroll-mt-20 px-6 py-20 text-white sm:py-28" aria-labelledby="search-heading">
      <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
        <div className="mb-6 grid size-24 place-items-center rounded-full border-2 border-dashed border-blue-200/40 bg-blue-900/60 text-5xl shadow-[0_0_45px_rgba(96,165,250,0.15)]" role="img" aria-label="Placeholder mascot logo">
          🙂
        </div>
        <h2 id="search-heading" className="text-3xl font-semibold tracking-tight sm:text-4xl">What are you looking for?</h2>
        <p className="mt-3 max-w-lg text-base leading-7 text-blue-100/70">
          Search for a product to start comparing prices.
        </p>
        <form className="mt-8 flex w-full flex-col gap-3 rounded-2xl border border-blue-200/15 bg-[#0b1d35]/80 p-2 shadow-xl shadow-black/20 backdrop-blur-sm sm:flex-row" role="search" onSubmit={handleSearch}>
          <label htmlFor="product-search" className="sr-only">Search products</label>
          <input
            id="product-search"
            name="query"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            placeholder="Try “laptop” or “coffee maker”"
            className="min-w-0 flex-1 rounded-xl bg-transparent px-4 py-3 text-base text-white outline-none placeholder:text-blue-100/45 focus-visible:ring-2 focus-visible:ring-blue-400"
          />
          <button type="submit" disabled={isSearching} className="rounded-xl bg-blue-500 px-7 py-3 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-wait disabled:opacity-70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
            {isSearching ? 'Searching…' : 'Search'}
          </button>
        </form>
        {error && <p className="mt-4 text-sm text-rose-200" role="alert">{error}</p>}
      </div>
    </section>
  )
}

export default SearchSection
