import { useEffect, useRef, useState } from 'react'
import { isTechProduct } from './productEligibility'
import Icon from './Icon.jsx'
import CollectionPicker from './CollectionPicker.jsx'
import ProductCard from './ProductCard.jsx'
import ProductDetails from './ProductDetails.jsx'

const collections = [
  { id: 'bestbuy-picks', label: 'Best Buy Picks', icon: 'tag', retailer: 'Best Buy', endpoint: '/api/bestbuy-search' },
  { id: 'walmart-picks', label: 'Walmart Picks', icon: 'spark', retailer: 'Walmart', endpoint: '/api/walmart-search' },
  { id: 'all-time-lows', label: 'Lowest Current Prices', icon: 'trend',
    description: 'The lowest listed prices in the current catalog.' },
  { id: 'deep-discounts', label: 'High Discounts', icon: 'percent',
    description: 'Listings with verified regular and sale prices.' },
  { id: 'new-releases', label: 'Recently Observed', icon: 'clock',
    description: 'The latest product observations in the catalog.' },
]
const EMPTY_PRODUCTS = []
const allCollections = 'all'
const collectionOptions = [{ id: allCollections, label: 'No Filters', icon: 'filter' }, ...collections]

function ProductRail({ products, title, onPreview, showObserved = false, retailer }) {
  const rail = useRef(null)

  function scroll(direction) {
    const motionReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    rail.current?.scrollBy({ left: direction * rail.current.clientWidth, behavior: motionReduced ? 'instant' : 'smooth' })
  }

  return (
    <div className="rail-frame">
      {products.length > 1 && (
        <div className="rail-controls">
          <button type="button" className="icon-button" aria-label={`Show previous ${title} products`} onClick={() => scroll(-1)}>
            <Icon name="left" />
          </button>
          <button type="button" className="icon-button" aria-label={`Show more ${title} products`} onClick={() => scroll(1)}>
            <Icon name="right" />
          </button>
        </div>
      )}
      <div className="product-rail" ref={rail}>
        {products.map((product) => (
          <ProductCard key={product.id || product.product_url} product={product} layout="collection" retailer={retailer}
            badge={showObserved && product.scraped_at ? new Date(product.scraped_at).toLocaleDateString() : undefined}
            onPreview={onPreview} />
        ))}
      </div>
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
  return {
    products: (data.products || []).filter(isTechProduct),
    collection: data.collection,
    discounts: (data.discounts || []).filter(isTechProduct),
  }
}

function RetailerPicks({ retailer, endpoint, initialProducts, homepageLoading, onPreview, onDiscounts }) {
  const retailerId = retailer.toLowerCase().replaceAll(' ', '-')
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState(initialProducts.filter(isTechProduct))
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [searchStatus, setSearchStatus] = useState(null)

  useEffect(() => {
    setProducts(initialProducts.filter(isTechProduct))
    setSearchStatus(null)
  }, [initialProducts])

  async function handleSearch(event) {
    event.preventDefault()
    const searchQuery = query.trim()
    if (!searchQuery || isLoading || homepageLoading) return

    setIsLoading(true)
    setError('')
    try {
      const result = await requestRetailerProducts(endpoint, searchQuery)
      setProducts(result.products)
      setSearchStatus(result.collection)
      onDiscounts(endpoint, result.discounts)
    } catch (loadError) {
      setError(loadError.message || 'Could not load retailer products.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section aria-labelledby={`${retailerId}-picks-heading`}>
      <div className="collection-heading">
        <div>
          <h2 id={`${retailerId}-picks-heading`}><Icon name={retailer === 'Best Buy' ? 'tag' : 'spark'} /> {retailer} Picks</h2>
          <p className="page-description">Browse {retailer} picks or search its live and stored listings.</p>
        </div>
        <form className="search-form retailer-search" role="search" onSubmit={handleSearch} aria-busy={isLoading}>
          <Icon name="search" />
          <label htmlFor={`${retailerId}-product-search`} className="sr-only">Search {retailer} products</label>
          <input id={`${retailerId}-product-search`} type="search" value={query}
            onChange={event => setQuery(event.target.value)} maxLength={300} required autoComplete="off"
            placeholder={`Search ${retailer} products...`} />
          <button type="submit" className="action-button" disabled={isLoading || homepageLoading}>
            {isLoading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </div>
      {searchStatus && !error && !isLoading && (
        <p className="collection-status" role="status">
          {products.length} {products.length === 1 ? 'listing' : 'listings'} matched
          {' · '}{searchStatus.live_matches} live, {searchStatus.catalog_matches} stored
          {searchStatus.message && ` · ${searchStatus.message}`}
        </p>
      )}
      {error ? (
        <div className="state-box state-error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary-button" onClick={handleSearch}>Try again</button>
        </div>
      ) : isLoading || homepageLoading ? (
        <p className="state-box" role="status">{isLoading ? `Searching ${retailer} listings…` : `Loading ${retailer} picks…`}</p>
      ) : products.length === 0 ? (
        <p className="state-box">{searchStatus ? `No ${retailer} listings matched this search.` : `No ${retailer} picks are available yet.`}</p>
      ) : (
        <ProductRail products={products} title={`${retailer} Picks`} onPreview={onPreview} retailer={retailer} />
      )}
    </section>
  )
}

function DealsSection({ isActive = true, footer } = {}) {
  const [activeCollection, setActiveCollection] = useState(allCollections)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [productsByCollection, setProductsByCollection] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [discoveryErrors, setDiscoveryErrors] = useState([])
  const [reloadKey, setReloadKey] = useState(0)
  const [discountsByRetailer, setDiscountsByRetailer] = useState({})

  function rememberDiscounts(endpoint, discounts) {
    setDiscountsByRetailer(current => ({ ...current, [endpoint]: discounts }))
  }

  const discounts = new Map()
  for (const product of [...(productsByCollection['deep-discounts'] || EMPTY_PRODUCTS), ...Object.values(discountsByRetailer).flat()]) {
    discounts.set(product.product_url, product)
  }
  const highDiscounts = [...discounts.values()].sort((left, right) =>
    right.savings_percent - left.savings_percent || left.title.localeCompare(right.title)).slice(0, 12)

  useEffect(() => {
    if (!isActive) setSelectedProduct(null)
  }, [isActive])

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
          (data.collections || []).map((collection) => [collection.id, (collection.products || []).filter(isTechProduct)]),
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

  return (
    <section className="page-wrap page-enter discover-page" aria-labelledby="discover-heading">
      <h1 id="discover-heading">Discover <span className="page-accent">great finds.</span></h1>
      <p className="page-description">Browse retailer picks, current prices, and the latest catalog finds.</p>
      <CollectionPicker items={collectionOptions} selected={activeCollection} onSelect={setActiveCollection} isActive={isActive} />
      {error && (
        <div className="state-box state-error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary-button" onClick={() => setReloadKey(key => key + 1)}>Try again</button>
        </div>
      )}
      {!error && discoveryErrors.length > 0 && (
        <div className="collection-status" role="status">
          <details>
            <summary>Some retailer categories could not be loaded</summary>
            <ul>{discoveryErrors.map((message, index) => <li key={index}>{message}</li>)}</ul>
          </details>
        </div>
      )}
      {collections.map(collection => {
        const products = collection.id === 'deep-discounts' ? highDiscounts : productsByCollection[collection.id] || EMPTY_PRODUCTS
        return (
          <div key={collection.id} className="discover-collection" id={`discover-panel-${collection.id}`}
            hidden={activeCollection !== allCollections && activeCollection !== collection.id}>
            <div className="collection-content">
              {collection.retailer ? (
                <RetailerPicks retailer={collection.retailer} endpoint={collection.endpoint}
                  initialProducts={products} homepageLoading={isLoading} onPreview={setSelectedProduct} onDiscounts={rememberDiscounts} />
              ) : (
                <>
                  <div className="collection-heading">
                    <div>
                      <h2><Icon name={collection.icon} /> {collection.label}</h2>
                      <p className="page-description">{collection.description}</p>
                    </div>
                    <span className="collection-count">{products.length} {products.length === 1 ? 'pick' : 'picks'}</span>
                  </div>
                  {isLoading ? (
                    <p className="state-box" role="status">Loading real products from the catalog…</p>
                  ) : error ? null : products.length === 0 ? (
                    <p className="state-box">{collection.id === 'deep-discounts'
                      ? 'No verified discounts yet. Search Best Buy or Walmart to check for current discounts.'
                      : 'No products are available in this section yet.'}</p>
                  ) : (
                    <ProductRail products={products} title={collection.label} onPreview={setSelectedProduct}
                      showObserved={collection.id === 'new-releases'} />
                  )}
                </>
              )}
            </div>
          </div>
        )
      })}
      {footer}
      <ProductDetails product={isActive ? selectedProduct : null} onClose={() => setSelectedProduct(null)} />
    </section>
  )
}

export default DealsSection
