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

function formatPrice(price, currency = 'USD') {
  const amount = Number(price)
  if (!Number.isFinite(amount)) return `${price} ${currency}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
}

function SearchResults({ search, onBack }) {
  const products = search?.products || []

  return (
    <section id="search-results" className="relative z-10 min-h-[75vh] scroll-mt-20 px-6 pb-24 pt-20 text-white sm:px-10" aria-labelledby="search-results-heading">
      <div className="mx-auto max-w-7xl">
        <button type="button" onClick={onBack} className="mb-8 rounded-xl border border-blue-100/15 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
          ← Back to Shoppie
        </button>
        <div className="mb-10 border-b border-blue-100/10 pb-5">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-blue-200/70">Product search</p>
          <h2 id="search-results-heading" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Results for “{search?.query}”</h2>
          <p className="mt-3 text-blue-100/65" aria-live="polite">{products.length} {products.length === 1 ? 'product' : 'products'} found in your catalog</p>
        </div>

        {products.length === 0 ? (
          <div className="rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 px-6 py-14 text-center">
            <p className="text-xl font-semibold">No matching products yet</p>
            <p className="mt-2 text-blue-100/60">Try another search, or add more products to your Supabase catalog.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((product, index) => (
              <article key={product.id || product.product_url} className={`anim-scale-in d-${(index % 3) + 1} group flex min-h-[25rem] flex-col overflow-hidden rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 text-left shadow-lg shadow-black/10 transition duration-300 hover:-translate-y-1 hover:border-blue-200/30 hover:bg-[#102746] hover:shadow-xl hover:shadow-black/20`}>
                <div className="relative grid h-48 w-full place-items-center overflow-hidden bg-gradient-to-br from-blue-400/25 to-indigo-300/5">
                  <span className="absolute left-4 top-4 rounded-full border border-white/10 bg-[#071326]/70 px-3 py-1 text-xs font-semibold text-blue-100 backdrop-blur">{product.source || 'Catalog'}</span>
                  <span className="text-7xl drop-shadow-lg transition duration-300 group-hover:scale-110" aria-hidden="true">{getIcon(product.category)}</span>
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <p className="text-xs font-medium uppercase tracking-wider text-blue-200/55">{(product.category || 'Product').replaceAll('-', ' ')}</p>
                  <h3 className="mt-2 text-lg font-semibold">{product.title}</h3>
                  {product.description && <p className="mt-2 line-clamp-3 text-sm leading-6 text-blue-100/60">{product.description}</p>}
                  <div className="mt-auto flex items-baseline gap-2 pt-4">
                    <span className="anim-count-up text-2xl font-semibold">{formatPrice(product.price, product.currency)}</span>
                  </div>
                </div>
                <div className="px-5 pb-5">
                  <a href={product.product_url} target="_blank" rel="noreferrer" className="block w-full rounded-xl border border-blue-200/15 bg-blue-400/10 px-4 py-2.5 text-center text-sm font-semibold text-blue-100 transition hover:bg-blue-400/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">
                    View at {product.source || 'retailer'} ↗
                  </a>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

export default SearchResults
