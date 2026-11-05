import { useEffect, useRef, useState } from 'react'
import { getProductDescription } from './productDescription'

const collections = [
  {
    id: 'all-time-lows',
    title: 'Lowest current prices',
    description: 'Lowest current prices in our catalog; historical lows are not tracked.',
  },
  {
    id: 'deep-discounts',
    title: 'Deep discounts',
    description: 'Discounts appear when verified regular and sale prices are available.',
  },
  {
    id: 'new-releases',
    title: 'Recently observed',
    description: 'Most recently observed catalog products; release dates are not tracked.',
  },
  {
    id: 'bestbuy-picks',
    title: 'Best Buy picks',
    description: 'Live search-card listings across product categories from Best Buy.',
  },
  {
    id: 'walmart-picks',
    title: 'Walmart picks',
    description: 'Live search-card listings across product categories from Walmart.',
  },
]
const EMPTY_PRODUCTS = []

function formatPrice(price, currency = 'USD') {
  const amount = Number(price)
  if (!Number.isFinite(amount)) return `${price} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
}

function ProductArtwork({ product, badge, className = 'h-64 shrink-0' }) {
  const [imageFailed, setImageFailed] = useState(false)

  return (
    <div className={`relative grid w-full place-items-center overflow-hidden bg-white ${className}`}>
      {product.image_url && !imageFailed ? (
        <img
          src={product.image_url}
          alt={product.title}
          loading="lazy"
          decoding="async"
          onError={() => setImageFailed(true)}
          className="h-full w-full object-contain p-4"
        />
      ) : (
        <span className="text-6xl text-slate-400" aria-hidden="true">▧</span>
      )}
      {badge && <span className="absolute left-4 top-4 rounded-full bg-[#071326]/80 px-3 py-1 text-xs font-semibold text-white">{badge}</span>}
    </div>
  )
}

async function requestRetailerProducts(endpoint, query, signal) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || 'Could not load retailer products.')
  return data.products || []
}

function RetailerPicks({ retailer, endpoint, initialProducts, homepageLoading }) {
  const retailerId = retailer.toLowerCase().replaceAll(' ', '-')
  const [query, setQuery] = useState('laptop')
  const [products, setProducts] = useState(initialProducts)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setProducts(initialProducts)
  }, [initialProducts])

  async function handleSearch(event) {
    event.preventDefault()
    const searchQuery = query.trim()
    if (!searchQuery || isLoading || homepageLoading) return

    setIsLoading(true)
    setError('')
    try {
      setProducts(await requestRetailerProducts(endpoint, searchQuery))
    } catch (loadError) {
      setError(loadError.message || 'Could not load retailer products.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section aria-labelledby={`${retailerId}-picks-heading`}>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-blue-100/10 pb-4">
        <div>
          <h3 id={`${retailerId}-picks-heading`} className="text-xl font-semibold">{retailer} picks</h3>
          <p className="mt-1 text-sm text-blue-100/55">Live listings and prices from {retailer} search results.</p>
        </div>
        <form className="flex w-full gap-2 sm:w-auto" role="search" onSubmit={handleSearch}>
          <label htmlFor={`${retailerId}-product-search`} className="sr-only">Search {retailer} products</label>
          <input
            id={`${retailerId}-product-search`}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={300}
            required
            placeholder={`Search ${retailer}`}
            className="min-w-0 flex-1 rounded-xl border border-blue-100/15 bg-[#071326]/70 px-4 py-2 text-sm text-white outline-none placeholder:text-blue-100/40 focus-visible:ring-2 focus-visible:ring-blue-400 sm:w-64"
          />
          <button type="submit" disabled={isLoading || homepageLoading} className="rounded-xl bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-wait disabled:opacity-60">
            {isLoading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200/20 bg-rose-950/20 px-5 py-5 text-sm text-rose-100" role="alert">
          <p>{error}</p>
          <button type="button" onClick={handleSearch} className="mt-3 rounded-lg border border-rose-100/20 px-4 py-2 font-semibold transition hover:bg-white/5">
            Try again
          </button>
        </div>
      ) : isLoading || homepageLoading ? (
        <p className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/50 px-5 py-8 text-center text-sm text-blue-100/60" role="status">Loading live {retailer} listings…</p>
      ) : products.length === 0 ? (
        <p className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/50 px-5 py-8 text-center text-sm text-blue-100/60">No {retailer} listings matched this search.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => (
            <article key={product.product_url} className="flex flex-col overflow-hidden rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 shadow-lg shadow-black/10">
              <ProductArtwork product={product} badge={retailer} className="aspect-square shrink-0" />
              <div className="flex flex-1 flex-col p-5">
                <p className="text-xs font-medium uppercase tracking-wider text-blue-200/55">{(product.category || 'Product').replaceAll('-', ' ')}</p>
                <h4 className="mt-2 line-clamp-3 text-lg font-semibold">{product.title}</h4>
                <p className="mt-2 line-clamp-3 text-sm leading-6 text-blue-100/60">{getProductDescription(product)}</p>
                <p className="mt-auto flex flex-wrap items-baseline gap-2 pt-4">
                  <span className="text-2xl font-semibold">{formatPrice(product.price, product.currency)}</span>
                  {product.regular_price && <span className="text-sm text-blue-100/45 line-through">{formatPrice(product.regular_price, product.currency)}</span>}
                </p>
                <a href={product.product_url} target="_blank" rel="noreferrer" className="mt-4 block w-full rounded-xl border border-blue-200/15 bg-blue-400/10 px-4 py-2.5 text-center text-sm font-semibold text-blue-100 transition hover:bg-blue-400/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
                  View at {retailer} ↗
                </a>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function DealsSection() {
  const [selectedProduct, setSelectedProduct] = useState(null)
  const carouselRefs = useRef({})
  const [productsByCollection, setProductsByCollection] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [discoveryErrors, setDiscoveryErrors] = useState([])
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function loadDeals() {
      setIsLoading(true)
      setError('')
      try {
        const response = await fetch('/api/deals', { signal: controller.signal })
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('The local API is still running its older version. Restart it, then try again.')
        }
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || 'Could not load products from the catalog.')
        const collectionsById = Object.fromEntries(
          (data.collections || []).map((collection) => [collection.id, collection.products || []]),
        )
        setProductsByCollection(collectionsById)
        setDiscoveryErrors(data.discovery_errors || [])
      } catch (loadError) {
        if (loadError.name !== 'AbortError') {
          setError(loadError.message || 'Could not load homepage products. Start the local API and try again.')
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    loadDeals()
    return () => controller.abort()
  }, [reloadKey])

  const scrollProducts = (collectionId, direction) => {
    const carousel = carouselRefs.current[collectionId]
    if (!carousel) return

    carousel.scrollBy({
      left: direction * carousel.clientWidth,
      behavior: 'smooth',
    })
  }

  return (
    <section id="deals" className="relative z-10 scroll-mt-20 px-6 pb-24 pt-12 text-white sm:px-10 sm:pb-32" aria-labelledby="discover-heading">
      <div className="mx-auto max-w-7xl">
        <div className="mb-14 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-blue-200/70">Curated for you</p>
          <h2 id="discover-heading" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Discover great finds</h2>
          <p className="mx-auto mt-3 max-w-xl text-blue-100/65">Browse real products from our catalog, with current prices and retailer links.</p>
        </div>

        <div className="space-y-14">
          <RetailerPicks retailer="Best Buy" endpoint="/api/bestbuy-search" initialProducts={productsByCollection['bestbuy-picks'] || EMPTY_PRODUCTS} homepageLoading={isLoading} />
          <RetailerPicks retailer="Walmart" endpoint="/api/walmart-search" initialProducts={productsByCollection['walmart-picks'] || EMPTY_PRODUCTS} homepageLoading={isLoading} />
          {error && (
            <div className="rounded-2xl border border-rose-200/20 bg-rose-950/20 px-5 py-5 text-center text-sm text-rose-100" role="alert">
              <p>{error}</p>
              <button type="button" onClick={() => setReloadKey((key) => key + 1)} className="mt-3 rounded-lg border border-rose-100/20 px-4 py-2 font-semibold transition hover:bg-white/5">
                Try again
              </button>
            </div>
          )}
          {!error && discoveryErrors.length > 0 && (
            <p className="rounded-2xl border border-amber-200/20 bg-amber-950/20 px-5 py-4 text-sm text-amber-100" role="status">
              Some retailer categories could not be loaded: {discoveryErrors.join('; ')}
            </p>
          )}
          {collections.filter((collection) => !['bestbuy-picks', 'walmart-picks'].includes(collection.id)).map((collection) => {
            const products = productsByCollection[collection.id] || []
            return (
              <section key={collection.id} aria-labelledby={`collection-${collection.id}`}>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-blue-100/10 pb-4">
                <div>
                  <h3 id={`collection-${collection.id}`} className="anim-fade-left text-xl font-semibold">{collection.title}</h3>
                  <p className="mt-1 text-sm text-blue-100/55">{collection.description}</p>
                </div>
                <span className="text-xs font-medium uppercase tracking-wider text-blue-200/60">{products.length} picks</span>
              </div>

              {isLoading ? (
                <p className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/50 px-5 py-8 text-center text-sm text-blue-100/60" role="status">Loading real products from the catalog…</p>
              ) : error ? null : products.length === 0 ? (
                <p className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/50 px-5 py-8 text-center text-sm text-blue-100/60">
                  {collection.id === 'deep-discounts'
                    ? 'No verified sale prices were returned by Best Buy or Walmart right now.'
                    : 'No products are available in this section yet.'}
                </p>
              ) : (
                <div className="relative">
                  <button type="button" onClick={() => scrollProducts(collection.id, -1)} aria-label={`Show previous ${collection.title} products`} className="absolute -left-4 top-1/2 z-20 grid size-11 -translate-y-1/2 place-items-center rounded-full border border-blue-100/20 bg-[#0b1d35]/95 text-xl text-blue-100 shadow-lg shadow-black/30 backdrop-blur transition hover:scale-105 hover:border-blue-200/50 hover:bg-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 sm:-left-5">←</button>
                  <button type="button" onClick={() => scrollProducts(collection.id, 1)} aria-label={`Show more ${collection.title} products`} className="absolute -right-4 top-1/2 z-20 grid size-11 -translate-y-1/2 place-items-center rounded-full border border-blue-100/20 bg-[#0b1d35]/95 text-xl text-blue-100 shadow-lg shadow-black/30 backdrop-blur transition hover:scale-105 hover:border-blue-200/50 hover:bg-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 sm:-right-5">→</button>
                  <div ref={(element) => { carouselRefs.current[collection.id] = element }} className="scrollbar-hide flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth pb-2">
                    {products.map((product, index) => (
                      <article
                        key={product.id || product.product_url}
                        className={`anim-scale-in d-${(index % 3) + 1} group flex min-h-[25rem] basis-[85%] shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 text-left shadow-lg shadow-black/10 transition duration-300 hover:-translate-y-1 hover:border-blue-200/30 hover:bg-[#102746] hover:shadow-xl hover:shadow-black/20 sm:basis-[calc((100%_-_1rem)/2)] lg:basis-[calc((100%_-_2rem)/3)]`}
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedProduct(product)}
                          className="flex flex-1 flex-col text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-blue-300"
                          aria-label={`Preview ${product.title}`}
                        >
                          <ProductArtwork
                            product={product}
                            badge={collection.id === 'all-time-lows'
                              ? 'Lowest current price'
                              : collection.id === 'bestbuy-picks'
                                ? 'Best Buy'
                                : collection.id === 'walmart-picks'
                                  ? 'Walmart'
                                  : collection.id === 'deep-discounts'
                                    ? 'On sale'
                                    : 'Recently observed'}
                          />
                          <div className="flex flex-1 flex-col p-5">
                            <p className="text-xs font-medium uppercase tracking-wider text-blue-200/55">{(product.category || 'Product').replaceAll('-', ' ')}</p>
                            <h4 className="mt-2 line-clamp-3 text-lg font-semibold">{product.title}</h4>
                            <p className="mt-2 line-clamp-3 text-sm leading-6 text-blue-100/60">{getProductDescription(product)}</p>
                            {product.scraped_at && <p className="mt-2 text-xs text-blue-100/50">Observed: {new Date(product.scraped_at).toLocaleDateString()}</p>}
                            <div className="mt-auto flex items-baseline gap-2 pt-4">
                              <span className="anim-count-up text-2xl font-semibold">{formatPrice(product.price, product.currency)}</span>
                              {product.regular_price && (
                                <>
                                  <span className="text-sm text-blue-100/45 line-through">{formatPrice(product.regular_price, product.currency)}</span>
                                  {product.savings_percent > 0 && <span className="text-sm font-semibold text-emerald-300">{product.savings_percent}% off</span>}
                                </>
                              )}
                            </div>
                          </div>
                        </button>
                        <div className="px-5 pb-5">
                          <a href={product.product_url} target="_blank" rel="noreferrer" className="block w-full rounded-xl border border-blue-200/15 bg-blue-400/10 px-4 py-2.5 text-center text-sm font-semibold text-blue-100 transition hover:bg-blue-400/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
                            View at {product.source || 'retailer'} ↗
                          </a>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              )}
              </section>
            )
          })}
        </div>
      </div>

      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#030b16]/75 p-5 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedProduct(null) }}>
          <div className="w-full max-w-md rounded-3xl border border-blue-100/15 bg-[#102746] p-7 shadow-2xl shadow-black/40" role="dialog" aria-modal="true" aria-labelledby="product-dialog-title">
            <ProductArtwork product={selectedProduct} className="mb-6 aspect-square rounded-2xl" />
            <p className="mt-5 text-xs font-semibold uppercase tracking-wider text-blue-200/60">{selectedProduct.category} · {selectedProduct.source}</p>
            <h3 id="product-dialog-title" className="mt-2 text-2xl font-semibold">{selectedProduct.title}</h3>
            <p className="mt-3 leading-7 text-blue-100/70">{getProductDescription(selectedProduct)}</p>
            <div className="mt-6 flex items-center justify-between border-t border-blue-100/10 pt-5">
              <span className="text-2xl font-semibold">
                {formatPrice(selectedProduct.price, selectedProduct.currency)}
                {selectedProduct.regular_price && (
                  <span className="ml-2 text-sm text-blue-100/45 line-through">{formatPrice(selectedProduct.regular_price, selectedProduct.currency)}</span>
                )}
              </span>
              <button type="button" onClick={() => setSelectedProduct(null)} className="rounded-xl border border-blue-100/15 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">Close</button>
            </div>
            <a href={selectedProduct.product_url} target="_blank" rel="noreferrer" className="mt-4 block w-full rounded-xl bg-blue-500 px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-blue-400">
              View at {selectedProduct.source || 'retailer'} ↗
            </a>
          </div>
        </div>
      )}
    </section>
  )
}

export default DealsSection
