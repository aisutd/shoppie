import { useEffect, useState } from 'react'
import Icon from './Icon.jsx'
import ProductCard from './ProductCard.jsx'
import ProductDetails from './ProductDetails.jsx'
import Tabs from './Tabs.jsx'

const resultsPerBatch = 12

function SearchResults({ search, onNewSearch, onRefined, isActive = true }) {
  const products = search?.products || []
  const retailerGroups = [
    { source: 'bestbuy.com', name: 'Best Buy' },
    { source: 'walmart.com', name: 'Walmart' },
  ].map((retailer) => ({
    ...retailer,
    products: products.filter((product) => product.source === retailer.source),
  }))
  const otherProducts = products.filter(
    (product) => !retailerGroups.some((retailer) => retailer.source === product.source),
  )
  if (otherProducts.length) {
    retailerGroups.push({ source: 'other', name: 'Other retailers', products: otherProducts })
  }
  const collection = search?.collection
  const [selectedGroup, setSelectedGroup] = useState('all')
  const [visibleCount, setVisibleCount] = useState(resultsPerBatch)
  const groups = [{ source: 'all', name: 'All', products }, ...retailerGroups]
  const activeGroup = groups.find(group => group.source === selectedGroup) || groups[0]
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [followUp, setFollowUp] = useState('')
  const [isRefining, setIsRefining] = useState(false)
  const [refineError, setRefineError] = useState('')
  const visibleProducts = activeGroup.products.slice(0, visibleCount)
  const resultSource = collection?.result_source === 'hybrid' ? 'Live + stored results'
    : collection?.result_source === 'live' ? 'Live retailer results' : 'Stored catalog'
  const remainingQueryLength = Math.max(0, 300 - (search?.query?.trim().length || 0) - 2)

  useEffect(() => {
    if (!isActive) setSelectedProduct(null)
  }, [isActive])

  function selectGroup(group) {
    setSelectedGroup(group)
    setVisibleCount(resultsPerBatch)
  }

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
      setVisibleCount(resultsPerBatch)
    } catch (error) {
      setRefineError(error.message || 'Could not reach local search. Start the local API and try again.')
    } finally {
      setIsRefining(false)
    }
  }

  return (
    <section className="page-wrap page-enter listings-page" aria-labelledby="search-results-heading">
      <div className="listings-heading">
        <div>
          <h2 id="search-results-heading" tabIndex={-1}>Results for <span>“{search?.query}”</span></h2>
          <p className="page-description" aria-live="polite">
            {products.length} {products.length === 1 ? 'product' : 'products'} matched
            {' · '}{resultSource}
            {collection?.result_source === 'hybrid' && ` (${collection.live_matches} live, ${collection.catalog_matches} stored)`}
          </p>
        </div>
        <div className="refinement">
          <div className="refinement-heading">
            <label htmlFor="follow-up-search">Refine search</label>
            <button className="text-link" type="button" onClick={onNewSearch}>New search <Icon name="arrow" /></button>
          </div>
          <form className="search-form" role="search" onSubmit={handleRefine} aria-busy={isRefining}>
            <Icon name="search" />
            <input id="follow-up-search" name="followUp" type="text" value={followUp}
              onChange={event => setFollowUp(event.target.value)} maxLength={remainingQueryLength}
              required disabled={remainingQueryLength === 0 || isRefining} placeholder="e.g. under $1,200" />
            <button type="submit" className="action-button" disabled={isRefining || remainingQueryLength === 0 || !followUp.trim()}>
              {isRefining ? 'Refining…' : 'Update search'}
            </button>
          </form>
          {remainingQueryLength === 0 && <p className="field-feedback">Start a new search to enter more details.</p>}
          {refineError && <p className="field-feedback error-text" role="alert">{refineError}</p>}
        </div>
      </div>
      {collection && (
        <div className="collection-status" role="status">
          <p>{collection.message}</p>
          {collection.errors?.length > 0 && (
            <details>
              <summary>Collection details</summary>
              <ul>{collection.errors.map((message, index) => <li key={index}>{message}</li>)}</ul>
            </details>
          )}
        </div>
      )}
      <Tabs id="retailers" label="Filter results by retailer" selected={activeGroup.source}
        onSelect={selectGroup} items={groups.map(group => ({
          id: group.source, label: group.name, count: group.products.length,
        }))} />
      {groups.map(group => (
        <div key={group.source} id={`retailers-panel-${group.source}`} role="tabpanel"
          aria-labelledby={`retailers-tab-${group.source}`} hidden={group !== activeGroup}>
          {group === activeGroup && (group.products.length ? (
            <>
              <div className="listing-grid">
                {visibleProducts.map(product => <ProductCard key={product.id || product.product_url}
                  product={product} retailer={group.source === 'all' ? undefined : group.name} onPreview={setSelectedProduct} />)}
              </div>
              {group.products.length > resultsPerBatch && (
                <div className="result-batching">
                  <p role="status">Showing {visibleProducts.length} of {group.products.length} matches</p>
                  <button type="button" className="secondary-button" disabled={visibleProducts.length === group.products.length}
                    onClick={() => setVisibleCount(count => count + resultsPerBatch)}>Load more</button>
                </div>
              )}
            </>
          ) : (
            <div className="state-box">
              <h2>{group.source === 'all' ? 'No matching products' : `No matching ${group.name} listings`}</h2>
              <p>Try a product name or model number. Live searches may not return a listing that meets every specification.</p>
            </div>
          ))}
        </div>
      ))}
      <ProductDetails product={isActive ? selectedProduct : null} onClose={() => setSelectedProduct(null)} />
    </section>
  )
}

export default SearchResults
