# Shoppie Filter and Sort module

This folder contains the reusable React filter and sort module used by the search results page.

## Files

- `FilterSortPanel.jsx` renders responsive price, retailer, and sort controls; selected filter chips; clear-all; and a live matching-product count. The panel does not show category controls.
- `filterState.js` creates and clears state and removes an individual filter.
- `filterProducts.js` exports the reusable pure filtering/sorting function and sort-option definitions.
- `index.js` is the public module entry point.
- `filter-sort.css` contains module-scoped styles.
- `README.md` documents the API, connection, and limitations.

## Technology-only catalog results

The panel and `filterProducts()` only return products whose category is one of Shoppie's recognized technology categories (such as laptops, phones, monitors, and computer accessories). Legacy `electronics` records are included only when the product title contains recognizable technology product terms. Products in unrelated categories and unclassified records are excluded from results and counts. This is an in-memory check; it does not change catalog records or make another database request.

## Component contract

Pass the same product array returned by the existing search API as `products`. The component computes the matching and sorted array internally and reports it through `onProductsChange(filteredProducts)`. The callback is optional, so the panel can also be rendered by itself to show controls and the count. The component does not fetch data, edit product objects, or mutate the input array. An optional `resetKey` clears panel state when its value changes; `SearchResults.jsx` passes the current search response object so refinements and new searches start with clean filters.

```jsx
<FilterSortPanel
  products={search.products}
  onProductsChange={setVisibleProducts}
  resetKey={search}
/>
```

The existing `SearchResults.jsx` currently renders cards from `search.products`. To consume the callback, a future integration would store `visibleProducts` in `SearchResults`, render the card loop from that array, and render the panel above it. The callback should be a stable state setter or memoized callback.

## Pure function use

```js
import { filterProducts, createInitialFilterState } from './filter-sort/index.js'

const state = {
  ...createInitialFilterState(),
  category: 'laptops',
  minPrice: '500',
  maxPrice: '1500',
  source: 'bestbuy.com',
  sortBy: 'price-asc',
}

const visibleProducts = filterProducts(products, state)
```

Each populated category, retailer, and price bound is an additional AND condition when using the pure function. The panel exposes price range and retailer filters. Matching is case-insensitive for category and source. Price range filtering excludes products with missing or invalid prices because their eligibility cannot be established. Invalid prices and dates sort after valid ones. Equal sort values retain their previous relative order. `recommended` returns matches in their original order.

Supported sort keys are `recommended`, `price-asc`, `price-desc`, `recently-observed` (by `scraped_at`), and `name-asc` (by `title`).

State helpers:

- `createInitialFilterState()` creates the empty filter state.
- `removeFilter(state, key)` clears one of `category`, `minPrice`, `maxPrice`, or `source` while preserving the other selections and sort.
- `clearFilterState()` clears filters and resets sorting to recommended.
- `hasActiveFilters(state)` checks whether any filter is selected.

## Integration with SearchResults.jsx

The existing page already receives `{ query, products, collection }` from `App.jsx`. It could import the public component:

```jsx
import { FilterSortPanel } from './filter-sort/index.js'
```

The module is rendered in `SearchResults.jsx`. That component passes `search.products` into the panel, stores the callback output locally, and renders those results through the existing product-card markup. It combines retailers into one grid so price and name sorts are visible across all retailers. `App.jsx` and `SearchSection.jsx` continue to provide the same result object; they do not need to know about filter state. The card keeps each retailer's source badge and link.

For full-catalog filtering and accurate catalog-wide counts, the Python API would also need to accept filter/sort parameters and apply them before pagination, and return suitable facet/count information. The current browser receives a bounded search result set, not the entire catalog.

## Limitations

- This module is deliberately not integrated into the website because the requested scope forbids changes to existing files.
- Filters only operate on the array passed to the component. The existing API caps results, so this cannot reveal matching products omitted from that response.
- The panel's retailer choices are Best Buy and Walmart. Category filtering remains available to callers of the pure function, but there is no category control in the panel.
- Available structured fields are `category`, `price`, `source`, `scraped_at`, and `title`. Brand, rating, stock, release date, and hardware specification filters are unavailable in the current product model.
- “Recently Observed” uses `scraped_at`, which is the observation time and does not establish when the product was released.
- The module does not implement pagination, URL synchronization, server filtering, or persistent filter state.
