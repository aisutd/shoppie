import { useState } from 'react'
import Icon from './Icon.jsx'

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
      onResults({ query: searchQuery, products: data.products || [], collection: data.collection || null })
    } catch (searchError) {
      setError(searchError.message || 'Could not reach local search. Start the local API and try again.')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="primary-search">
      <form className="search-form search-form-primary" role="search" onSubmit={handleSearch} aria-busy={isSearching}>
        <Icon name="search" />
        <label htmlFor="product-search" className="sr-only">Search products</label>
        <input id="product-search" name="query" type="search" value={query}
          onChange={event => setQuery(event.target.value)} required autoComplete="off"
          placeholder='Try "laptop" to find great tech deals' />
        <button type="submit" className="action-button" disabled={isSearching}>
          {isSearching ? 'Searching…' : 'Search'} <Icon name="arrow" />
        </button>
      </form>
      {isSearching && (
        <p className="search-feedback" role="status">
          Checking Best Buy and Walmart for current listings, saving products, and finding matches. This can take a minute or longer.
        </p>
      )}
      {error && <p className="search-feedback error-text" role="alert">{error}</p>}
    </div>
  )
}

export default SearchSection
