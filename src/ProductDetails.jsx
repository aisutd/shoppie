import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import { Price, ProductArtwork, RetailerLabel, retailerName } from './ProductCard.jsx'
import { getProductDescription } from './productDescription'

export default function ProductDetails({ product, onClose }) {
  const dialog = useRef(null)
  const closeButton = useRef(null)
  const closeTimer = useRef(null)

  useEffect(() => {
    if (!product) return
    const panel = dialog.current
    const trigger = document.activeElement
    const overflow = document.body.style.overflow
    panel.showModal()
    panel.scrollTop = 0
    document.body.style.overflow = 'hidden'
    closeButton.current?.focus({ preventScroll: true })
    return () => {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
      panel.classList.remove('is-closing')
      if (panel.open) panel.close()
      document.body.style.overflow = overflow
      if (trigger?.isConnected) trigger.focus({ preventScroll: true })
    }
  }, [product])

  function close() {
    if (closeTimer.current !== null) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onClose()
      return
    }
    dialog.current.classList.add('is-closing')
    closeTimer.current = setTimeout(onClose, 180)
  }

  return (
    <dialog ref={dialog} className="product-panel" aria-labelledby={product ? 'product-panel-title' : undefined}
      onCancel={event => { event.preventDefault(); close() }}
      onClick={event => { if (event.target === event.currentTarget) close() }}>
      {product && (
        <div className="product-panel-inner">
          <div className="product-panel-top">
            <span>Product details</span>
            <button className="icon-button" type="button" ref={closeButton} onClick={close} aria-label="Close product details">
              <Icon name="close" />
            </button>
          </div>
          <ProductArtwork product={product} className="product-panel-image" />
          {product.image_credit && (
            <p className="image-credit">
              <a href={product.image_credit.source_url} target="_blank" rel="noreferrer">Photo by {product.image_credit.author}</a>
              {' · '}
              <a href={product.image_credit.license_url} target="_blank" rel="noreferrer">{product.image_credit.license}</a>
              {product.image_credit.note && ` · ${product.image_credit.note}`}
            </p>
          )}
          <div className="product-panel-heading">
            <div className="product-card-meta">
              <RetailerLabel product={product} />
              {product.category && <span className="product-category">{product.category.replaceAll('-', ' ')}</span>}
            </div>
            <h2 id="product-panel-title">{product.title}</h2>
            <Price product={product} />
          </div>
          <section className="product-panel-section">
            <h3>Description</h3>
            <p>{getProductDescription(product)}</p>
          </section>
          {product.match_reason && (
            <section className="product-panel-section">
              <h3>Why this matches</h3>
              <p>{product.match_reason}</p>
            </section>
          )}
          {product.scraped_at && (
            <p className="observed-time">Observed <time dateTime={product.scraped_at}>{new Date(product.scraped_at).toLocaleString()}</time></p>
          )}
          {product.product_url && (
            <a className="action-button panel-retailer" href={product.product_url} target="_blank" rel="noreferrer">
              View at {retailerName(product)} <Icon name="external" />
            </a>
          )}
        </div>
      )}
    </dialog>
  )
}
