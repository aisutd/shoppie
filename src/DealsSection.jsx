import { useRef, useState } from 'react'

const collections = [
  {
    id: 'all-time-lows',
    title: 'All-time low prices',
    description: 'Prices worth a second look.',
    products: [
      { id: 'headphones', name: 'QuietSound Pro Headphones', category: 'Audio', price: '$179', oldPrice: '$249', note: 'Lowest price tracked', icon: '🎧', tone: 'from-blue-400/25 to-indigo-300/5', detail: 'Wireless over-ear headphones with active noise cancellation and up to 30 hours of battery life.' },
      { id: 'monitor', name: 'ViewWide 27” Monitor', category: 'Computer displays', price: '$229', oldPrice: '$299', note: 'New price low', icon: '🖥️', tone: 'from-cyan-300/20 to-blue-400/5', detail: 'A 27-inch QHD display placeholder with an adjustable stand and slim bezels.' },
      { id: 'earbuds', name: 'Pulse Mini Earbuds', category: 'Audio', price: '$49', oldPrice: '$79', note: 'Lowest price tracked', icon: '🎵', tone: 'from-sky-300/20 to-blue-400/5', detail: 'Compact wireless earbuds placeholder with a pocket charging case and clear everyday sound.' },
      { id: 'ssd', name: 'SwiftStore 2TB SSD', category: 'Storage', price: '$109', oldPrice: '$159', note: 'New price low', icon: '💾', tone: 'from-indigo-300/20 to-blue-400/5', detail: 'A portable 2TB solid-state drive placeholder for fast backups and extra storage.' },
      { id: 'webcam', name: 'ClearView HD Webcam', category: 'Computer accessories', price: '$39', oldPrice: '$69', note: 'Lowest price tracked', icon: '📷', tone: 'from-blue-300/20 to-cyan-400/5', detail: 'A plug-and-play HD webcam placeholder for video calls and streaming.' },
      { id: 'router', name: 'MeshWave Wi-Fi Router', category: 'Networking', price: '$129', oldPrice: '$189', note: 'New price low', icon: '📡', tone: 'from-cyan-300/20 to-indigo-400/5', detail: 'A mesh-ready Wi-Fi router placeholder for reliable coverage around the home.' },
    ],
  },
  {
    id: 'deep-discounts',
    title: 'Deep discounts',
    description: 'Big drops on popular tech.',
    products: [
      { id: 'keyboard', name: 'KeyCraft Wireless Keyboard', category: 'Accessories', price: '$69', oldPrice: '$119', note: 'Save 42%', icon: '⌨️', tone: 'from-violet-300/20 to-blue-400/5', detail: 'A compact wireless mechanical keyboard placeholder with backlit keys and multi-device pairing.' },
      { id: 'speaker', name: 'RoomBeat Smart Speaker', category: 'Smart home', price: '$59', oldPrice: '$99', note: 'Save 40%', icon: '🔊', tone: 'from-sky-300/20 to-indigo-400/5', detail: 'A small smart speaker placeholder for music, timers, and voice assistant features.' },
      { id: 'mouse', name: 'Glide Pro Wireless Mouse', category: 'Accessories', price: '$34', oldPrice: '$59', note: 'Save 42%', icon: '🖱️', tone: 'from-blue-300/20 to-violet-400/5', detail: 'An ergonomic wireless mouse placeholder with adjustable sensitivity and quiet clicks.' },
      { id: 'charger', name: 'QuickCharge 3-in-1 Stand', category: 'Chargers', price: '$39', oldPrice: '$65', note: 'Save 40%', icon: '🔋', tone: 'from-indigo-300/20 to-sky-400/5', detail: 'A foldable charging stand placeholder for a phone, earbuds, and smartwatch.' },
      { id: 'camera', name: 'SnapGo Action Camera', category: 'Cameras', price: '$149', oldPrice: '$229', note: 'Save 35%', icon: '🎥', tone: 'from-cyan-300/20 to-blue-400/5', detail: 'A compact action camera placeholder with image stabilization and a waterproof case.' },
      { id: 'dock', name: 'PortHub USB-C Dock', category: 'Computer accessories', price: '$79', oldPrice: '$129', note: 'Save 39%', icon: '🔌', tone: 'from-violet-300/20 to-cyan-400/5', detail: 'A USB-C hub placeholder with multiple display, USB, and card-reader ports.' },
    ],
  },
  {
    id: 'new-releases',
    title: 'New releases',
    description: 'Fresh picks to keep on your radar.',
    products: [
      { id: 'phone', name: 'Nova X Smartphone', category: 'Phones', price: '$799', oldPrice: null, note: 'Just released', icon: '📱', tone: 'from-blue-300/25 to-sky-400/5', detail: 'A new phone placeholder with a bright edge-to-edge display and an all-day battery.' },
      { id: 'tablet', name: 'NoteTab Air', category: 'Tablets', price: '$499', oldPrice: null, note: 'Just released', icon: '📲', tone: 'from-indigo-300/20 to-cyan-300/5', detail: 'A lightweight tablet placeholder for reading, streaming, and everyday notes.' },
      { id: 'watch', name: 'TrackOne Smartwatch', category: 'Wearables', price: '$249', oldPrice: null, note: 'Just released', icon: '⌚', tone: 'from-cyan-300/20 to-blue-400/5', detail: 'A new smartwatch placeholder with activity tracking and a bright always-on display.' },
      { id: 'laptop', name: 'AirNote 14 Laptop', category: 'Computers', price: '$1,099', oldPrice: null, note: 'Just released', icon: '💻', tone: 'from-blue-300/20 to-indigo-400/5', detail: 'A slim laptop placeholder designed for everyday work, study, and streaming.' },
      { id: 'console', name: 'PlayBox Handheld', category: 'Gaming', price: '$399', oldPrice: null, note: 'Just released', icon: '🎮', tone: 'from-violet-300/20 to-blue-400/5', detail: 'A portable gaming system placeholder with a vivid screen and detachable controls.' },
      { id: 'buds', name: 'StudioBuds Max', category: 'Audio', price: '$199', oldPrice: null, note: 'Just released', icon: '🎧', tone: 'from-sky-300/20 to-indigo-400/5', detail: 'New wireless earbuds placeholder featuring adaptive audio and a compact charging case.' },
    ],
  },
]

function DealsSection() {
  const [selectedProduct, setSelectedProduct] = useState(null)
  const carouselRefs = useRef({})

  const scrollProducts = (collectionId, direction) => {
    const carousel = carouselRefs.current[collectionId]
    if (!carousel) return

    carousel.scrollBy({
      left: direction * carousel.clientWidth,
      behavior: 'smooth',
    })
  }

  return (
    <section className="relative z-10 px-6 pb-24 pt-12 text-white sm:px-10 sm:pb-32" aria-labelledby="discover-heading">
      <div className="mx-auto max-w-7xl">
        <div className="mb-14 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-blue-200/70">Curated for you</p>
          <h2 id="discover-heading" className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Discover great finds</h2>
          <p className="mx-auto mt-3 max-w-xl text-blue-100/65">Catch record-low prices, standout discounts, and new tech worth watching.</p>
        </div>

        <div className="space-y-14">
          {collections.map((collection) => (
            <section key={collection.id} aria-labelledby={`collection-${collection.id}`}>
              <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-blue-100/10 pb-4">
                <div>
                  <h3 id={`collection-${collection.id}`} className="anim-fade-left text-xl font-semibold">{collection.title}</h3>
                  <p className="mt-1 text-sm text-blue-100/55">{collection.description}</p>
                </div>
                <span className="text-xs font-medium uppercase tracking-wider text-blue-200/60">{collection.products.length} picks</span>
              </div>

              <div className="relative">
                <button type="button" onClick={() => scrollProducts(collection.id, -1)} aria-label={`Show previous ${collection.title} products`} className="absolute -left-4 top-1/2 z-20 grid size-11 -translate-y-1/2 place-items-center rounded-full border border-blue-100/20 bg-[#0b1d35]/95 text-xl text-blue-100 shadow-lg shadow-black/30 backdrop-blur transition hover:scale-105 hover:border-blue-200/50 hover:bg-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 sm:-left-5">←</button>
                <button type="button" onClick={() => scrollProducts(collection.id, 1)} aria-label={`Show more ${collection.title} products`} className="absolute -right-4 top-1/2 z-20 grid size-11 -translate-y-1/2 place-items-center rounded-full border border-blue-100/20 bg-[#0b1d35]/95 text-xl text-blue-100 shadow-lg shadow-black/30 backdrop-blur transition hover:scale-105 hover:border-blue-200/50 hover:bg-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300 sm:-right-5">→</button>
                <div ref={(element) => { carouselRefs.current[collection.id] = element }} className="scrollbar-hide flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth pb-2">
                  {collection.products.map((product, index) => (
                    <article
                      key={product.id}
                      className={`anim-scale-in d-${(index % 3) + 1} group flex min-h-[25rem] basis-[85%] shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-blue-100/10 bg-[#0b1d35]/70 text-left shadow-lg shadow-black/10 transition duration-300 hover:-translate-y-1 hover:border-blue-200/30 hover:bg-[#102746] hover:shadow-xl hover:shadow-black/20 sm:basis-[calc((100%_-_1rem)/2)] lg:basis-[calc((100%_-_2rem)/3)]`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedProduct(product)}
                        className="flex flex-1 flex-col text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-blue-300"
                        aria-label={`Preview ${product.name}`}
                      >
                        <div className={`relative grid h-48 w-full place-items-center overflow-hidden bg-gradient-to-br ${product.tone}`}>
                          <span className="absolute left-4 top-4 rounded-full border border-white/10 bg-[#071326]/70 px-3 py-1 text-xs font-semibold text-blue-100 backdrop-blur">{product.note}</span>
                          <span className="text-7xl drop-shadow-lg transition duration-300 group-hover:scale-110" aria-hidden="true">{product.icon}</span>
                        </div>
                        <div className="flex flex-1 flex-col p-5">
                          <p className="text-xs font-medium uppercase tracking-wider text-blue-200/55">{product.category}</p>
                          <h4 className="mt-2 text-lg font-semibold">{product.name}</h4>
                          <div className="mt-auto flex items-baseline gap-2 pt-4">
                            <span className="anim-count-up text-2xl font-semibold">{product.price}</span>
                            {product.oldPrice && <span className="text-sm text-blue-100/40 line-through">{product.oldPrice}</span>}
                          </div>
                        </div>
                      </button>
                      <div className="px-5 pb-5">
                        <button type="button" disabled title="A product listing link will be added here" className="w-full cursor-not-allowed rounded-xl border border-blue-200/15 bg-blue-400/10 px-4 py-2.5 text-sm font-semibold text-blue-100/60">
                          Product link coming soon
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            </section>
          ))}
        </div>
      </div>

      {selectedProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#030b16]/75 p-5 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedProduct(null) }}>
          <div className="w-full max-w-md rounded-3xl border border-blue-100/15 bg-[#102746] p-7 shadow-2xl shadow-black/40" role="dialog" aria-modal="true" aria-labelledby="product-dialog-title">
            <div className="mb-6 grid h-40 place-items-center rounded-2xl bg-gradient-to-br from-blue-500/20 to-sky-300/5 text-7xl" aria-hidden="true">{selectedProduct.icon}</div>
            <p className="text-xs font-semibold uppercase tracking-wider text-blue-200/60">{selectedProduct.category} · {selectedProduct.note}</p>
            <h3 id="product-dialog-title" className="mt-2 text-2xl font-semibold">{selectedProduct.name}</h3>
            <p className="mt-3 leading-7 text-blue-100/70">{selectedProduct.detail}</p>
            <div className="mt-6 flex items-center justify-between border-t border-blue-100/10 pt-5">
              <div><span className="text-2xl font-semibold">{selectedProduct.price}</span>{selectedProduct.oldPrice && <span className="ml-2 text-sm text-blue-100/40 line-through">{selectedProduct.oldPrice}</span>}</div>
              <button type="button" onClick={() => setSelectedProduct(null)} className="rounded-xl border border-blue-100/15 px-4 py-2 text-sm font-semibold text-blue-100 transition hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300">Close</button>
            </div>
            <p className="mt-4 text-xs text-blue-100/40">Example product and price for layout preview.</p>
          </div>
        </div>
      )}
    </section>
  )
}

export default DealsSection
