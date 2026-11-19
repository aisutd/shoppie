const SORT_OPTIONS = new Set([
  'recommended',
  'price-asc',
  'price-desc',
  'recently-observed',
  'name-asc',
])

const TECH_CATEGORIES = new Set([
  'cameras',
  'computer-accessories',
  'gaming',
  'headphones',
  'keyboards',
  'laptop-accessories',
  'laptops',
  'mice',
  'monitors',
  'phones',
  'speakers',
  'storage',
  'tablets',
  'televisions',
])

const TECH_TITLE_PATTERN = /\b(?:laptops?|notebooks?|macbooks?|chromebooks?|thinkpads?|zenbooks?|vivobooks?|ideapads?|smartphones?|cell phones?|iphones?|galaxy\s+s\d+|pixel\s+\d+|ipads?|tablets?|headphones?|earbuds?|airpods|monitors?|computer displays?|keyboards?|mice|computer mice|cameras?|speakers?|soundbars?|televisions?|tvs?|playstation|xbox|nintendo switch|game controllers?|game consoles?|ssds?|hard drives?|flash drives?|chargers?|adapters?|docks?|hubs?|webcams?|smartwatches?|wearables?|routers?|network switches?|power banks?)\b/i

function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function timestamp(value) {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

/** Filter by every active constraint, then sort the matches. Does not mutate inputs. */
export function filterProducts(products = [], state = {}) {
  if (!Array.isArray(products)) return []

  const minPrice = state.minPrice === '' || state.minPrice == null ? null : finiteNumber(state.minPrice)
  const maxPrice = state.maxPrice === '' || state.maxPrice == null ? null : finiteNumber(state.maxPrice)
  const category = String(state.category || '').trim().toLocaleLowerCase()
  const source = normalizeSource(state.source)

  const matches = products.filter((product) => {
    if (!isTechProduct(product)) return false
    if (category && String(product.category || '').trim().toLocaleLowerCase() !== category) return false
    if (source && normalizeSource(product.source) !== source) return false

    if (minPrice !== null || maxPrice !== null) {
      const price = finiteNumber(product.price)
      // A product with no usable price cannot be verified against a price range.
      if (price === null || (minPrice !== null && price < minPrice) || (maxPrice !== null && price > maxPrice)) return false
    }
    return true
  })

  const sortBy = SORT_OPTIONS.has(state.sortBy) ? state.sortBy : 'recommended'
  if (sortBy === 'recommended') return matches

  return matches
    .map((product, index) => ({ product, index }))
    .sort((a, b) => {
      let comparison = 0
      if (sortBy === 'price-asc' || sortBy === 'price-desc') {
        const left = finiteNumber(a.product.price)
        const right = finiteNumber(b.product.price)
        if (left === null || right === null) comparison = left === right ? 0 : left === null ? 1 : -1
        else comparison = sortBy === 'price-asc' ? left - right : right - left
      } else if (sortBy === 'recently-observed') {
        const left = timestamp(a.product.scraped_at)
        const right = timestamp(b.product.scraped_at)
        if (left === null || right === null) comparison = left === right ? 0 : left === null ? 1 : -1
        else comparison = right - left
      } else if (sortBy === 'name-asc') {
        comparison = String(a.product.title || '').localeCompare(String(b.product.title || ''), undefined, { sensitivity: 'base' })
      }
      return comparison || a.index - b.index
    })
    .map(({ product }) => product)
}

/** Only include recognized technology categories; legacy electronics rows need title evidence. */
export function isTechProduct(product) {
  if (!product || typeof product !== 'object') return false
  const category = String(product.category || '').trim().toLocaleLowerCase()
  if (TECH_CATEGORIES.has(category)) return true
  return category === 'electronics' && TECH_TITLE_PATTERN.test(String(product.title || ''))
}

function normalizeSource(value) {
  const normalized = String(value || '')
    .trim()
    .toLocaleLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .split('/')[0]
    .replace(/\s+/g, '')
  if (normalized === 'bestbuy' || normalized === 'bestbuy.com') return 'bestbuy.com'
  if (normalized === 'walmart' || normalized === 'walmart.com') return 'walmart.com'
  return normalized
}

export const FILTER_SORT_OPTIONS = [
  { value: 'recommended', label: 'Recommended' },
  { value: 'price-asc', label: 'Price: Low to High' },
  { value: 'price-desc', label: 'Price: High to Low' },
  { value: 'recently-observed', label: 'Recently Observed' },
  { value: 'name-asc', label: 'Product Name: A to Z' },
]

