/** Create the initial filter and sort state. Empty strings mean no price bound. */
export function createInitialFilterState() {
  return {
    category: '',
    minPrice: '',
    maxPrice: '',
    source: '',
    sortBy: 'recommended',
  }
}

/** Return only the filtering fields, clearing the sort choice as well. */
export function clearFilterState() {
  return createInitialFilterState()
}

/** Remove one filter while retaining all other active filters and sort order. */
export function removeFilter(state, key) {
  if (!['category', 'minPrice', 'maxPrice', 'source'].includes(key)) return { ...state }
  return { ...state, [key]: '' }
}

export function hasActiveFilters(state) {
  return Boolean(state.category || state.source || state.minPrice !== '' || state.maxPrice !== '')
}

