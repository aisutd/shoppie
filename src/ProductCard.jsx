import { useState } from 'react'
import Icon from './Icon.jsx'

const retailerNames = {
  'bestbuy.com': 'Best Buy',
  'walmart.com': 'Walmart',
  'amazon.com': 'Amazon',
  'target.com': 'Target',
}

export function retailerName(product, fallback = 'Retailer') {
  return retailerNames[product.source] || product.source || fallback
}

export function formatPrice(price, currency = 'USD') {
  if (price == null || price === '') return 'Price unavailable'
  const amount = Number(price)
  if (!Number.isFinite(amount)) return `${price} ${currency}`
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
  } catch {
    return `${price} ${currency}`
  }
}

export function ProductArtwork({ product, className = '' }) {
  const [failedImage, setFailedImage] = useState(null)
  const hasImage = product.image_url && product.image_url !== failedImage
  return (
    <div className={`product-artwork ${hasImage ? 'has-image' : ''} ${className}`}>
      {hasImage ? <img src={product.image_url} alt={product.title} loading="lazy" decoding="async"
        onError={() => setFailedImage(product.image_url)} /> : <Icon name="image" />}
    </div>
  )
}

export function Price({ product }) {
  if (product.is_reference && (product.price == null || product.price === '')) {
    return <span className="unpriced-label">Check price at retailer</span>
  }
  return (
    <div className="product-price">
      <strong>{formatPrice(product.price, product.currency)}</strong>
      {product.regular_price != null && product.regular_price !== '' &&
        <del aria-label={`Regular price ${formatPrice(product.regular_price, product.currency)}`}>
          {formatPrice(product.regular_price, product.currency)}
        </del>}
      {product.savings_percent > 0 && <span className="savings-label">{product.savings_percent}% off</span>}
    </div>
  )
}

export default function ProductCard({ product, onPreview, layout = 'listing', retailer, badge }) {
  const name = retailerName(product, retailer || 'Catalog')
  return (
    <article className={`product-card product-card-${layout}`}>
      <div className="product-card-content">
        <ProductArtwork product={product} />
        <div className="product-card-copy">
          <p className="product-card-meta"><RetailerLabel product={product} name={name} />
            {product.category && <span className="product-category">{product.category.replaceAll('-', ' ')}</span>}
          </p>
          <h3><button type="button" className="product-card-preview" title={product.title}
            aria-label={`View details for ${product.title}`} onClick={event => {
              event.currentTarget.focus({ preventScroll: true })
              onPreview(product)
            }}>{product.title}</button></h3>
          {badge && <span className="observation-badge">{badge}</span>}
          <Price product={product} />
        </div>
      </div>
      {product.product_url && (
        <a className="product-card-link" href={product.product_url} target="_blank" rel="noreferrer"
          aria-label={`View at ${name}: ${product.title} (opens in a new tab)`} title={`View at ${name}`}>
          <Icon name="external" />
        </a>
      )}
    </article>
  )
}

export function RetailerLabel({ product, name = retailerName(product) }) {
  return (
    <span className={`retailer-name ${product.source === 'bestbuy.com' ? 'retailer-bestbuy' : product.source === 'walmart.com' ? 'retailer-walmart' : ''}`}>
      <Icon name={product.source === 'walmart.com' ? 'spark' : 'tag'} /> {name}
    </span>
  )
}
