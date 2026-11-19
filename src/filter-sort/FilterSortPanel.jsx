import { useEffect, useMemo, useState } from 'react'
import { filterProducts, FILTER_SORT_OPTIONS, isTechProduct } from './filterProducts.js'
import { clearFilterState, createInitialFilterState, hasActiveFilters, removeFilter } from './filterState.js'
import './filter-sort.css'

/**
 * Standalone controls for a product array. onProductsChange receives the
 * filtered/sorted array; the component does not fetch data or alter its input.
 */
export default function FilterSortPanel({ products = [], onProductsChange, className = '', resetKey }) {
  const [filterModel, setFilterModel] = useState(() => ({
    resetKey,
    state: createInitialFilterState(),
  }))
  const state = Object.is(filterModel.resetKey, resetKey)
    ? filterModel.state
    : createInitialFilterState()

  if (!Object.is(filterModel.resetKey, resetKey)) {
    setFilterModel({ resetKey, state })
  }

  const techProducts = useMemo(
    () => (Array.isArray(products) ? products.filter(isTechProduct) : []),
    [products],
  )
  const filteredProducts = useMemo(() => filterProducts(techProducts, state), [techProducts, state])
  const sources = [
    { value: 'bestbuy.com', label: 'Best Buy' },
    { value: 'walmart.com', label: 'Walmart' },
  ]

  useEffect(() => {
    onProductsChange?.(filteredProducts)
  }, [filteredProducts, onProductsChange])

  function update(key, value) {
    setFilterModel((current) => ({
      ...current,
      state: { ...current.state, [key]: value },
    }))
  }

  function clearAll() {
    setFilterModel({ resetKey, state: clearFilterState() })
  }

  const activeFilters = [
    state.minPrice !== '' && { key: 'minPrice', label: `Min: ${formatPrice(state.minPrice)}` },
    state.maxPrice !== '' && { key: 'maxPrice', label: `Max: ${formatPrice(state.maxPrice)}` },
    state.source && { key: 'source', label: `Retailer: ${retailerName(state.source)}` },
  ].filter(Boolean)

  return (
    <section className={`shoppie-filter-sort ${className}`} aria-label="Filter and sort products">
      <div className="sfs-heading">
        <div>
          <h2>Filter &amp; Sort</h2>
          <p aria-live="polite">{filteredProducts.length} {filteredProducts.length === 1 ? 'product' : 'products'} shown</p>
        </div>
        <button type="button" className="sfs-clear" onClick={clearAll} disabled={!hasActiveFilters(state) && state.sortBy === 'recommended'}>Clear all</button>
      </div>

      <div className="sfs-controls">
        <fieldset className="sfs-field sfs-price-field">
          <legend>Price range</legend>
          <div className="sfs-price-inputs">
            <label><span className="sfs-visually-hidden">Minimum price</span><input aria-label="Minimum price" type="number" min="0" step="0.01" inputMode="decimal" placeholder="Min $" value={state.minPrice} onChange={(event) => update('minPrice', event.target.value)} /></label>
            <span aria-hidden="true">to</span>
            <label><span className="sfs-visually-hidden">Maximum price</span><input aria-label="Maximum price" type="number" min="0" step="0.01" inputMode="decimal" placeholder="Max $" value={state.maxPrice} onChange={(event) => update('maxPrice', event.target.value)} /></label>
          </div>
        </fieldset>

        <label className="sfs-field">
          <span>Retailer</span>
          <select value={state.source} onChange={(event) => update('source', event.target.value)}>
            <option value="">All retailers ({techProducts.length})</option>
            {sources.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>

        <label className="sfs-field">
          <span>Sort by</span>
          <select value={state.sortBy} onChange={(event) => update('sortBy', event.target.value)}>
            {FILTER_SORT_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>

      {activeFilters.length > 0 && (
        <div className="sfs-active" aria-label="Selected filters">
          <span className="sfs-active-title">Active filters</span>
          {activeFilters.map(({ key, label }) => (
            <button key={key} type="button" className="sfs-chip" onClick={() => setFilterModel((current) => ({ ...current, state: removeFilter(current.state, key) }))} aria-label={`Remove ${label}`}>
              {label}<span aria-hidden="true"> ×</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

function formatPrice(value) {
  const number = Number(value)
  return Number.isFinite(number) ? new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(number) : String(value)
}

function retailerName(source) {
  const knownRetailers = {
    'amazon.com': 'Amazon',
    amazon: 'Amazon',
    'bestbuy.com': 'Best Buy',
    bestbuy: 'Best Buy',
    'best buy': 'Best Buy',
    'target.com': 'Target',
    target: 'Target',
    'walmart.com': 'Walmart',
    walmart: 'Walmart',
  }
  const normalized = source
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/^www\./i, '')
    .split('/')[0]
    .toLocaleLowerCase()
  return knownRetailers[normalized] || normalized.replace(/\.com$/i, '').replace(/^./, (character) => character.toLocaleUpperCase())
}
