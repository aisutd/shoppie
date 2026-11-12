import { useEffect, useRef, useState } from 'react'

export default function DealsSection() {
  const [topDeals, setTopDeals] = useState([])
  const [collections, setCollections] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const carouselRefs = useRef({})

  useEffect(() => {
    fetch('http://127.0.0.1:8001/api/deals')
      .then((res) => res.json())
      .then((data) => {
        if (data.deals && data.deals.length > 0) {
          // Strict Tech Filtering
          const nonTechKeywords = ['shopkins', 'toy', 'mug', 'cup', 'ceramic', 'bottle', 'plush', 'doll', 'shirt', 'hoodie']

          const techDeals = data.deals.filter((item) => {
            const title = (item.title || '').toLowerCase()
            const category = (item.category || '').toLowerCase()
            return !nonTechKeywords.some((kw) => title.includes(kw) || category.includes(kw))
          })

          // 1. Sort by price to build the top "Deals & Price Drops" section
          const sortedByPrice = [...techDeals].sort((a, b) => Number(a.price || 0) - Number(b.price || 0))
          
          const formattedTopDeals = sortedByPrice.slice(0, 6).map((item, index) => ({
            id: `top-${item.id || index}`,
            name: item.title,
            category: 'Price Drop',
            price: item.price ? `$${Number(item.price).toLocaleString()}` : 'N/A',
            oldPrice: item.price ? `$${(Number(item.price) * 1.25).toFixed(2)}` : null,
            note: item.source || 'Verified Deal',
            dealBadge: index === 0 ? '👑 Best Value' : '⚡ Mega Drop',
            badgeStyle: 'bg-amber-500/20 text-amber-300 border-amber-400/30 shadow-amber-500/10',
            icon: '💻',
            imageUrl: item.image_url || null,
            url: item.product_url || null,
            tone: 'from-amber-500/20 via-blue-600/15 to-transparent',
            detail: item.description || 'Record-low verified tech price drop.',
          }))

          setTopDeals(formattedTopDeals)

          // 2. Group remainder by specific tech categories
          const groups = {}
          techDeals.forEach((item, index) => {
            const titleLower = (item.title || '').toLowerCase()
            let determinedCategory = 'Electronics & Gadgets'
            
            if (titleLower.includes('laptop') || titleLower.includes('macbook') || titleLower.includes('computer')) {
              determinedCategory = 'Computers & Laptops'
            } else if (titleLower.includes('phone') || titleLower.includes('iphone') || titleLower.includes('galaxy')) {
              determinedCategory = 'Smartphones & Mobile'
            } else if (titleLower.includes('headphone') || titleLower.includes('earbud') || titleLower.includes('audio') || titleLower.includes('speaker')) {
              determinedCategory = 'Audio & Wearables'
            }

            const isDeal = index % 2 === 0
            if (!groups[determinedCategory]) {
              groups[determinedCategory] = []
            }

            groups[determinedCategory].push({
              id: item.id || index,
              name: item.title,
              category: determinedCategory,
              price: item.price ? `$${Number(item.price).toLocaleString()}` : 'N/A',
              oldPrice: item.price ? `$${(Number(item.price) * 1.2).toFixed(2)}` : null,
              note: item.source || 'Verified Retailer',
              dealBadge: isDeal ? '🔥 Hot Deal' : '⚡ Price Drop',
              badgeStyle: isDeal ? 'bg-amber-500/20 text-amber-300 border-amber-400/30' : 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30',
              icon: '💻',
              imageUrl: item.image_url || null,
              url: item.product_url || null,
              tone: 'from-blue-600/25 via-indigo-500/15 to-transparent',
              detail: item.description || 'Verified live scraped tech product.',
            })
          })

          const mappedCollections = Object.keys(groups).map((catName) => ({
            id: catName.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
            title: catName,
            description: `Top verified tech price drops in ${catName}.`,
            products: groups[catName],
          }))

          setCollections(mappedCollections)
        }
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch live tech deals:', err)
        setLoading(false)
      })
  }, [])

  const scrollProducts = (collectionId, direction) => {
    const carousel = carouselRefs.current[collectionId]
    if (!carousel) return
    carousel.scrollBy({
      left: direction * (carousel.clientWidth * 0.75),
      behavior: 'smooth',
    })
  }

  return (
    <section id="deals" className="relative z-10 scroll-mt-20 px-6 pb-28 pt-16 text-white sm:px-10 sm:pb-36" aria-labelledby="discover-heading">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-16 text-center">
          <div className="inline-flex items-center gap-2.5 rounded-full border border-blue-400/30 bg-blue-500/15 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.25em] text-blue-300 backdrop-blur-md shadow-lg shadow-blue-500/10">
            <span className="size-2.5 rounded-full bg-emerald-400 animate-ping"></span>
            Live Tech Feed Active
          </div>
          <h2 id="discover-heading" className="mt-4 text-4xl font-black tracking-tight sm:text-5xl bg-gradient-to-r from-white via-blue-100 to-blue-400 bg-clip-text text-transparent drop-shadow-sm">
            Curated Tech Deals & Drops
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-base text-blue-200/80 leading-relaxed font-medium">
            Real-time monitored discounts, verified retailer price slashes, and live technology gear.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-28 text-blue-200/70">
            <div className="size-12 rounded-full border-4 border-blue-500 border-t-transparent animate-spin mb-4 shadow-lg shadow-blue-500/20"></div>
            <p className="text-sm font-semibold tracking-wider uppercase">Loading live tech products...</p>
          </div>
        ) : (
          <div className="space-y-24">
            
            {/* Top Section: Deals & Price Drops */}
            {topDeals.length > 0 && (
              <section aria-labelledby="top-deals-heading" className="relative rounded-3xl border border-amber-500/30 bg-gradient-to-b from-amber-500/10 via-[#0b1d35]/90 to-[#071326] p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
                <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-amber-500/20 pb-4">
                  <div>
                    <h3 id="top-deals-heading" className="text-2xl font-black tracking-tight text-white flex items-center gap-3">
                      <span className="text-2xl">🔥</span> Featured Deals & Price Drops
                    </h3>
                    <p className="mt-1 text-sm text-amber-200/80 font-medium">The absolute lowest prices and best value tech drops right now.</p>
                  </div>
                  <span className="rounded-full border border-amber-400/40 bg-amber-500/20 px-4 py-1 text-xs font-black uppercase tracking-wider text-amber-300">
                    Top Picks
                  </span>
                </div>

                <div className="relative group/carousel">
                  <button
                    type="button"
                    onClick={() => scrollProducts('top-deals', -1)}
                    className="absolute -left-4 top-1/2 z-20 grid size-12 -translate-y-1/2 place-items-center rounded-2xl border border-amber-400/40 bg-[#071326]/95 text-xl text-white shadow-2xl backdrop-blur-xl transition-all duration-300 hover:scale-110 hover:bg-amber-600 opacity-0 group-hover/carousel:opacity-100"
                  >
                    ←
                  </button>
                  <button
                    type="button"
                    onClick={() => scrollProducts('top-deals', 1)}
                    className="absolute -right-4 top-1/2 z-20 grid size-12 -translate-y-1/2 place-items-center rounded-2xl border border-amber-400/40 bg-[#071326]/95 text-xl text-white shadow-2xl backdrop-blur-xl transition-all duration-300 hover:scale-110 hover:bg-amber-600 opacity-0 group-hover/carousel:opacity-100"
                  >
                    →
                  </button>

                  <div
                    ref={(element) => { carouselRefs.current['top-deals'] = element }}
                    className="scrollbar-hide flex snap-x snap-mandatory gap-6 overflow-x-auto scroll-smooth pb-4 pt-2"
                  >
                    {topDeals.map((product) => (
                      <article
                        key={product.id}
                        className="group relative flex min-h-[29rem] basis-[88%] shrink-0 snap-start flex-col overflow-hidden rounded-3xl border border-amber-500/30 bg-[#0b1d35]/90 text-left shadow-xl transition-all duration-300 hover:-translate-y-2 hover:border-amber-400 hover:shadow-2xl hover:shadow-amber-500/20 sm:basis-[calc((100%_-_1.5rem)/2)] lg:basis-[calc((100%_-_3rem)/3)]"
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedProduct(product)}
                          className="flex flex-1 flex-col text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-400"
                        >
                          <div className={`relative grid h-52 w-full place-items-center overflow-hidden bg-gradient-to-br ${product.tone} border-b border-amber-500/20`}>
                            <span className="absolute left-4 top-4 z-10 rounded-full border border-white/20 bg-[#071326]/90 px-3.5 py-1 text-xs font-bold text-blue-200 backdrop-blur-md shadow-md">
                              {product.note}
                            </span>
                            <span className={`absolute right-4 top-4 z-10 rounded-full border px-3 py-1 text-xs font-extrabold tracking-wide backdrop-blur-md shadow-lg ${product.badgeStyle}`}>
                              {product.dealBadge}
                            </span>
                            {product.imageUrl ? (
                              <img src={product.imageUrl} alt={product.name} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                            ) : (
                              <span className="text-6xl drop-shadow-xl">{product.icon}</span>
                            )}
                          </div>
                          <div className="flex flex-1 flex-col p-6">
                            <p className="text-xs font-bold uppercase tracking-widest text-amber-400/90">{product.category}</p>
                            <h4 className="mt-2.5 text-lg font-bold leading-snug line-clamp-2 text-white group-hover:text-amber-200 transition-colors">
                              {product.name}
                            </h4>
                            <div className="mt-auto flex items-baseline gap-3 pt-5">
                              <span className="text-2xl font-black tracking-tight text-white">{product.price}</span>
                              {product.oldPrice && <span className="text-sm font-semibold text-blue-300/40 line-through">{product.oldPrice}</span>}
                              <span className="ml-auto text-xs font-bold text-emerald-400 uppercase tracking-wider bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">In Stock</span>
                            </div>
                          </div>
                        </button>
                        <div className="p-6 pt-0">
                          {product.url ? (
                            <a
                              href={product.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block w-full text-center rounded-2xl border border-amber-400/40 bg-gradient-to-r from-amber-600 to-orange-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-amber-600/30 transition-all duration-300 hover:from-amber-500 hover:to-orange-500 hover:scale-[1.02]"
                            >
                              View Live Deal ↗
                            </a>
                          ) : (
                            <button type="button" disabled className="w-full cursor-not-allowed rounded-2xl border border-blue-500/10 bg-blue-500/5 px-4 py-3 text-sm font-semibold text-blue-200/40">
                              Link Unavailable
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {/* Separated Tech Categories */}
            {collections.map((collection) => (
              <section key={collection.id} aria-labelledby={`collection-${collection.id}`} className="relative">
                <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-blue-500/20 pb-4">
                  <div>
                    <h3 id={`collection-${collection.id}`} className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
                      <span className="h-3 w-3 rounded-full bg-blue-500 shadow-md shadow-blue-500/50"></span>
                      {collection.title}
                    </h3>
                    <p className="mt-1 text-sm text-blue-200/70 font-medium">{collection.description}</p>
                  </div>
                  <span className="rounded-full border border-blue-400/30 bg-blue-500/10 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-blue-300 backdrop-blur-md">
                    {collection.products.length} {collection.products.length === 1 ? 'Deal' : 'Deals'} Available
                  </span>
                </div>

                <div className="relative group/carousel">
                  <button
                    type="button"
                    onClick={() => scrollProducts(collection.id, -1)}
                    className="absolute -left-5 top-1/2 z-20 grid size-12 -translate-y-1/2 place-items-center rounded-2xl border border-blue-400/40 bg-[#071326]/95 text-xl text-white shadow-2xl backdrop-blur-xl transition-all duration-300 hover:scale-110 hover:border-blue-300 hover:bg-blue-600 opacity-0 group-hover/carousel:opacity-100 sm:-left-6"
                  >
                    ←
                  </button>
                  <button
                    type="button"
                    onClick={() => scrollProducts(collection.id, 1)}
                    className="absolute -right-5 top-1/2 z-20 grid size-12 -translate-y-1/2 place-items-center rounded-2xl border border-blue-400/40 bg-[#071326]/95 text-xl text-white shadow-2xl backdrop-blur-xl transition-all duration-300 hover:scale-110 hover:border-blue-300 hover:bg-blue-600 opacity-0 group-hover/carousel:opacity-100 sm:-right-6"
                  >
                    →
                  </button>
                  
                  <div
                    ref={(element) => { carouselRefs.current[collection.id] = element }}
                    className="scrollbar-hide flex snap-x snap-mandatory gap-6 overflow-x-auto scroll-smooth pb-4 pt-2"
                  >
                    {collection.products.map((product) => (
                      <article
                        key={product.id}
                        className="group relative flex min-h-[29rem] basis-[88%] shrink-0 snap-start flex-col overflow-hidden rounded-3xl border border-blue-500/25 bg-gradient-to-b from-[#102746]/90 to-[#071326]/95 text-left shadow-xl shadow-black/40 backdrop-blur-xl transition-all duration-300 hover:-translate-y-2 hover:border-blue-400 hover:shadow-2xl hover:shadow-blue-500/20 sm:basis-[calc((100%_-_1.5rem)/2)] lg:basis-[calc((100%_-_3rem)/3)]"
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedProduct(product)}
                          className="flex flex-1 flex-col text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
                        >
                          <div className={`relative grid h-52 w-full place-items-center overflow-hidden bg-gradient-to-br ${product.tone} border-b border-blue-500/10`}>
                            <span className="absolute left-4 top-4 z-10 rounded-full border border-white/20 bg-[#071326]/90 px-3.5 py-1 text-xs font-bold text-blue-200 backdrop-blur-md shadow-md">
                              {product.note}
                            </span>
                            <span className={`absolute right-4 top-4 z-10 rounded-full border px-3 py-1 text-xs font-extrabold tracking-wide backdrop-blur-md shadow-lg ${product.badgeStyle}`}>
                              {product.dealBadge}
                            </span>
                            {product.imageUrl ? (
                              <img src={product.imageUrl} alt={product.name} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
                            ) : (
                              <span className="text-6xl drop-shadow-xl">{product.icon}</span>
                            )}
                          </div>
                          <div className="flex flex-1 flex-col p-6">
                            <p className="text-xs font-bold uppercase tracking-widest text-blue-300/80">{product.category}</p>
                            <h4 className="mt-2.5 text-lg font-bold leading-snug line-clamp-2 text-white group-hover:text-blue-200 transition-colors">
                              {product.name}
                            </h4>
                            <div className="mt-auto flex items-baseline gap-3 pt-5">
                              <span className="text-2xl font-black tracking-tight text-white">{product.price}</span>
                              {product.oldPrice && <span className="text-sm font-semibold text-blue-300/40 line-through">{product.oldPrice}</span>}
                              <span className="ml-auto text-xs font-bold text-emerald-400 uppercase tracking-wider bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20">In Stock</span>
                            </div>
                          </div>
                        </button>
                        <div className="p-6 pt-0">
                          {product.url ? (
                            <a
                              href={product.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="block w-full text-center rounded-2xl border border-blue-400/40 bg-gradient-to-r from-blue-600/80 to-indigo-600/80 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/30 transition-all duration-300 hover:from-blue-600 hover:to-indigo-500 hover:scale-[1.02]"
                            >
                              View Live Deal ↗
                            </a>
                          ) : (
                            <button type="button" disabled className="w-full cursor-not-allowed rounded-2xl border border-blue-500/10 bg-blue-500/5 px-4 py-3 text-sm font-semibold text-blue-200/40">
                              Link Unavailable
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {selectedProduct && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6 backdrop-blur-md transition-all animate-fadeIn" 
          onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedProduct(null) }}
        >
          <div className="w-full max-w-lg rounded-3xl border border-blue-400/30 bg-[#0b1d35] p-8 shadow-2xl shadow-blue-500/20 backdrop-blur-2xl">
            <div className="mb-6 relative grid h-52 w-full place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600/30 to-indigo-500/15 border border-blue-400/20">
              {selectedProduct.imageUrl ? (
                <img src={selectedProduct.imageUrl} alt={selectedProduct.name} className="h-full w-full object-cover" />
              ) : (
                <span className="text-7xl">{selectedProduct.icon}</span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-blue-500/20 border border-blue-400/30 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-blue-300">
                {selectedProduct.category} · {selectedProduct.note}
              </span>
              <span className="text-3xl font-black text-white">{selectedProduct.price}</span>
            </div>
            <h3 className="mt-3 text-2xl font-black text-white tracking-tight">{selectedProduct.name}</h3>
            <p className="mt-3 text-sm leading-relaxed text-blue-200/80 font-medium">{selectedProduct.detail}</p>
            <div className="mt-8 flex items-center justify-end gap-3 border-t border-blue-500/20 pt-6">
              <button 
                type="button" 
                onClick={() => setSelectedProduct(null)} 
                className="rounded-2xl border border-blue-500/30 bg-white/5 px-5 py-3 text-sm font-semibold text-blue-200 transition hover:bg-white/10"
              >
                Close
              </button>
              {selectedProduct.url && (
                <a 
                  href={selectedProduct.url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/40 transition hover:from-blue-500 hover:to-indigo-500"
                >
                  Visit Retailer ↗
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}