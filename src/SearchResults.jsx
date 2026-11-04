import { useEffect, useState } from 'react'

const categoryIcons = {
  audio: '🎧',
  computer: '💻',
  laptop: '💻',
  phone: '📱',
  tablet: '📱',
  camera: '📷',
  gaming: '🎮',
  tv: '📺',
  smart: '🏠',
}

function getIcon(category = '') {
  const normalized = category.toLowerCase()
  const match = Object.entries(categoryIcons).find(([keyword]) => normalized.includes(keyword))
  return match?.[1] || '🛍️'
}

function ProductArtwork({ product, className, showSource = false }) {
  const [imageFailed, setImageFailed] = useState(false)
  const hasImage = product.image_url && !imageFailed

  return (
    <div className={`relative grid place-items-center overflow-hidden bg-white ${className}`}>
      {hasImage ? (
        <img
          src={product.image_url}
          alt={product.title}
          loading="lazy"
          decoding="async"
          onError={() => setImageFailed(true)}
          className="h-full w-full object-contain p-6"
        />
      ) : (
        <span className="text-7xl text-slate-400" aria-hidden="true">{getIcon(product.category)}</span>
      )}
      {showSource && <span className="absolute left-4 top-4 rounded-full border border-white/10 bg-[#071326]/70 px-3 py-1 text-xs font-semibold text-blue-100 backdrop-blur">{product.source || 'Catalog'}</span>}
    </div>
  )
}

function formatPrice(price, currency = 'USD') {
  const amount = Number(price)
  if (!Number.isFinite(amount)) return `${price} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
}

function SearchResults({ search, onBack, onRefined }) {
  const products = search?.products || []
  const collection = search?.collection
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [followUp, setFollowUp] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [refineError, setRefineError] = useState('')
  const remainingQueryLength = Math.max(0, 300 - (search?.query?.trim().length || 0) - 2)

  async function handleRefine(event) {
    event.preventDefault()
    const detail = followUp.trim()
    if (!detail || isRefining) return

    const refinedQuery = `${search.query.trim()}; ${detail}`
    setIsRefining(true)
    setRefineError('')
    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: refinedQuery }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Could not refine this search. Please try again.')
      onRefined({
        ...search,
        query: refinedQuery,
        products: data.products || [],
        collection: data.collection || null,
      })
      setFollowUp('')
    } catch (error) {
      setRefineError(error.message || 'Could not reach local search. Start the local API and try again.')
    } finally {
      setIsRefining(false)
    }
  }

  useEffect(() => {
    if (!selectedProduct) return undefined
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setSelectedProduct(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedProduct])

  return (
    <section id="search-results" className="relative z-10 min-h-[75vh] scroll-mt-20 px-6 pb-24 pt-20 text-white sm:px-10" aria-labelledby="search-results-heading">
      <div className="mx-auto max-w-7xl">
        <button type="button" onClick={onBack} className="mb-8 rounded-xl border border-blue-100/15 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
          ← Back to Shoppie
        </button>
        <div className="mb-10 border-b border-blue-100/10 pb-5">
          <h2 id="search-results-heading" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Results for “{search?.query}”</h2>
          <p className="mt-3 text-blue-100/65" aria-live="polite">
            {products.length} {products.length === 1 ? 'product' : 'products'} matched
            {collection?.result_source === 'live' ? ' from this live Best Buy search' : ' in the stored catalog'}
          </p>
          {collection && (
            <div className="mt-4 rounded-xl border border-blue-100/15 bg-[#071326]/40 p-4 text-sm text-blue-100/75" role="status">
              <p>{collection.message}</p>
              {collection.errors?.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer">Collection details</summary>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {collection.errors.map((message, index) => <li key={index}>{message}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        <form
          className="mb-8 rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 p-5 sm:flex sm:items-end sm:gap-4"
          role="search"
          onSubmit={handleRefine}
        >
          <div className="min-w-0 flex-1">
            <label htmlFor="follow-up-search" className="block text-sm font-semibold text-white">
              Looking for something more specific?
            </label>
            <p className="mt-1 text-sm text-blue-100/60">
              Add a detail to narrow these results, like a budget, screen size, or memory amount.
            </p>
            <input
              id="follow-up-search"
              name="followUp"
              type="text"
              value={followUp}
              onChange={(event) => setFollowUp(event.target.value)}
              maxLength={remainingQueryLength}
              required
              disabled={remainingQueryLength === 0 || isRefining}
              placeholder="e.g. under $1,200 with at least 16 GB RAM"
              className="mt-3 w-full rounded-xl border border-blue-100/15 bg-[#071326]/70 px-4 py-3 text-white outline-none placeholder:text-blue-100/40 focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-50"
            />
          </div>
          <button
            type="submit"
            disabled={isRefining || remainingQueryLength === 0 || !followUp.trim()}
            className="mt-3 w-full rounded-xl bg-blue-500 px-5 py-3 font-semibold text-white transition hover:bg-blue-400 disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 sm:mt-0 sm:w-auto"
          >
            {isRefining ? 'Refining…' : 'Update search'}
          </button>
          {refineError && <p className="mt-3 text-sm text-rose-200 sm:basis-full" role="alert">{refineError}</p>}
        </form>

        {products.length === 0 ? (
          <div className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 px-6 py-14 text-center">
            <p className="text-xl font-semibold">No matching products yet</p>
            <p className="mt-2 text-blue-100/60">Try a product name or model number. A live check can fail or find listings that do not meet your requirements.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product, index) => (
              <article key={product.id || product.product_url} className={`anim-scale-in d-${(index % 3) + 1} group flex min-h-[27rem] flex-col overflow-hidden rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 text-left shadow-lg shadow-black/10 transition duration-300 hover:-translate-y-1 hover:border-blue-200/30 hover:bg-[#102746] hover:shadow-xl hover:shadow-black/20`}>
                <button type="button" onClick={() => setSelectedProduct(product)} aria-label={`View details for ${product.title}`} className="flex flex-1 flex-col text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-blue-300">
                  <ProductArtwork product={product} className="h-52 w-full shrink-0 transition duration-300 group-hover:scale-[1.02]" showSource />
                  <div className="flex flex-1 flex-col p-5">
                    <p className="text-xs font-medium uppercase tracking-wider text-blue-200/55">{(product.category || 'Product').replaceAll('-', ' ')}</p>
                    <h3 className="mt-2 min-h-[5.25rem] line-clamp-3 text-lg font-semibold leading-7">{product.title}</h3>
                    {product.scraped_at && <p className="mt-2 text-xs text-blue-100/50">Observed: {new Date(product.scraped_at).toLocaleString()}</p>}
                    {product.description && <p className="mt-2 line-clamp-3 text-sm leading-6 text-blue-100/60">{product.description}</p>}
                    <p className="mt-3 line-clamp-2 text-xs leading-5 text-blue-200/70"><span className="font-semibold text-blue-100">Why this match:</span> {product.match_reason}</p>
                    <div className="mt-auto flex items-baseline gap-2 pt-4">
                      <span className="anim-count-up text-2xl font-semibold">{formatPrice(product.price, product.currency)}</span>
                    </div>
                  </div>
                </button>
                <div className="px-5 pb-7 pt-2">
                  <a href={product.product_url} target="_blank" rel="noreferrer" className="block w-full rounded-xl border border-blue-200/15 bg-blue-400/10 px-4 py-3 text-center text-sm font-semibold text-blue-100 transition hover:bg-blue-400/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
                    View at {product.source || 'retailer'} ↗
                  </a>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#030b16]/75 p-5 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedProduct(null) }}>
          <div className="max-h-[calc(100vh-2.5rem)] w-full max-w-md overflow-y-auto overscroll-contain rounded-3xl border border-blue-100/15 bg-[#102746] p-7 shadow-2xl shadow-black/40" role="dialog" aria-modal="true" aria-labelledby="search-product-dialog-title">
            <ProductArtwork key={selectedProduct.id || selectedProduct.product_url} product={selectedProduct} className="mb-6 aspect-square w-full rounded-2xl" />
            <p className="text-xs font-semibold uppercase tracking-wider text-blue-200/60">{(selectedProduct.category || 'Product').replaceAll('-', ' ')} · {selectedProduct.source || 'Catalog'}</p>
            <h3 id="search-product-dialog-title" className="mt-2 text-2xl font-semibold">{selectedProduct.title}</h3>
            <p className="mt-3 leading-7 text-blue-100/70">{selectedProduct.description || 'No additional description is available for this product.'}</p>
            <div className="mt-4 rounded-xl border border-blue-100/10 bg-[#071326]/40 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-blue-200/60">Why this result</p>
              <p className="mt-2 text-sm leading-6 text-blue-100/75">{selectedProduct.match_reason}</p>
            </div>
            <div className="mt-6 flex items-center justify-between gap-3 border-t border-blue-100/10 pt-5">
              <span className="text-2xl font-semibold">{formatPrice(selectedProduct.price, selectedProduct.currency)}</span>
              <button type="button" onClick={() => setSelectedProduct(null)} className="rounded-xl border border-blue-100/15 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">Close</button>
            </div>
            <a href={selectedProduct.product_url} target="_blank" rel="noreferrer" className="mt-4 block w-full rounded-xl bg-blue-500 px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
              View at {selectedProduct.source || 'retailer'} ↗
            </a>
          </div>
        </div>
      )}
    </section>
  )
}

export default SearchResults
