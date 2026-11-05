const productTypes = [
  {
    pattern: /\b(laptops?|notebooks?|chromebooks?|desktops?|computers?|pc)\b/i,
    label: 'computer',
    details: 'Review the listed processor, memory, storage, and screen configuration.',
  },
  {
    pattern: /\b(monitors?|displays?|screens?)\b/i,
    label: 'display',
    details: 'Compare the listed screen size, resolution, refresh rate, and connectivity.',
  },
  {
    pattern: /\b(phones?|smartphones?|cell phones?|iphones?)\b/i,
    label: 'phone',
    details: 'Check storage, carrier compatibility, and included accessories.',
  },
  {
    pattern: /\b(headphones?|earbuds?|earphones?|speakers?)\b/i,
    label: 'audio product',
    details: 'Review the listed connection type, fit, and audio features.',
  },
  {
    pattern: /\b(game|gaming|controller|console)\b/i,
    label: 'gaming product',
    details: 'Check platform compatibility and the included accessories.',
  },
  {
    pattern: /\b(toys?|games?|lego|figures?)\b/i,
    label: 'toy or game',
    details: 'Review the recommended age range and what is included.',
  },
  {
    pattern: /\b(mug|coffee|kitchen|cookware)\b/i,
    label: 'kitchen product',
    details: 'Check the listed size, materials, and care instructions.',
  },
  {
    pattern: /\b(camera|camcorder)\b/i,
    label: 'camera',
    details: 'Review the listed resolution, lens or zoom details, and included equipment.',
  },
  {
    pattern: /\b(tv|television)\b/i,
    label: 'television',
    details: 'Compare the listed screen size, resolution, and connectivity.',
  },
]

export function getProductDescription(product) {
  const providedDescription = typeof product?.description === 'string'
    ? product.description.trim()
    : ''
  if (providedDescription) return providedDescription

  const title = typeof product?.title === 'string' ? product.title.trim() || 'This item' : 'This item'
  const category = typeof product?.category === 'string'
    ? product.category.replaceAll('-', ' ').trim()
    : ''
  const searchableText = `${title} ${category || ''}`
  const productType = productTypes.find(({ pattern }) => pattern.test(searchableText))
  const label = productType?.label || (category && !['other', 'electronics'].includes(category.toLowerCase())
    ? category
    : 'product')
  const details = productType?.details || 'Review the listing for its specifications and other product details.'

  const article = /^[aeiou]/i.test(label) ? 'an' : 'a'
  return `${title} is listed as ${article} ${label}. ${details} Visit the retailer page to confirm full specifications, compatibility, included items, and current availability.`
}
