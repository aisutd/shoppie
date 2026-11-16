// Keep these conservative exclusions aligned with scraper/live_search.py.
// Unknown products stay eligible; category labels alone are not a tech allowlist.
const nonTechCategories = new Set([
  'toys-games', 'kitchen-dining', 'home-garden', 'clothing', 'office-supplies',
  'toys', 'apparel', 'furniture', 'groceries', 'beauty', 'sports-outdoors',
  'toys-and-games', 'kitchen', 'kitchenware', 'home-decor', 'home-goods',
])
const nonTechTitles = /\b(?:toys?|shopkins|dolls?|action figures?|playsets?|plush|stuffed animals?|board games?|puzzles?|mugs?|cups?|tumblers?|drinkware|cookware|dinnerware|plates?|bowls?|kitchen|furniture|bedding|garden|patio|decor|lamps?|rugs?|curtains?|shirts?|jackets?|shoes|sneakers|clothing|apparel|spiral notebooks?|binders?|pens?|paper|office supplies)\b/i
const obviousNonTech = /\blego\b.*\b(?:building|bricks?|sets?)\b|\bbarbie\s+(?:dreamhouse|dolls?)\b|\bkitchenaid\b.*\bmixers?\b/i

export function isTechProduct(product) {
  const category = String(product.category || '').trim().toLowerCase().replaceAll('_', '-')
  const title = String(product.title || '')
  return !nonTechCategories.has(category) && !nonTechTitles.test(title)
    && !(obviousNonTech.test(title) && !/\bvideo\s+games?\b/i.test(title))
}
