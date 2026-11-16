// Run with node --test src/navigation.test.cjs; uses existing build dependencies.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { transformSync } = require('esbuild')
const eligibilityModule = { exports: {} }
vm.runInNewContext(transformSync(fs.readFileSync(`${__dirname}/productEligibility.js`, 'utf8'), {
  loader: 'js', format: 'cjs',
}).code, { module: eligibilityModule, exports: eligibilityModule.exports })

function harness(file, globals = {}, testExports = '') {
  const states = []
  let cursor = 0
  let effects = []
  const react = {
    createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useState(initial) {
      const index = cursor++
      if (!(index in states)) states[index] = initial
      return [states[index], value => { states[index] = value }]
    },
    useEffect: effect => { effects.push(effect) },
    useRef: initial => react.useState({ current: initial })[0],
  }
  const module = { exports: {} }
  const code = transformSync(fs.readFileSync(`${__dirname}/${file}`, 'utf8') + testExports, {
    loader: 'jsx', format: 'cjs', jsxFactory: 'React.createElement',
  }).code
  vm.runInNewContext(code, {
    module, exports: module.exports, React: react,
    require: name => name === 'react' ? react
      : name.includes('useSmoothWheelScroll') ? { __esModule: true, default: () => {} }
      : name.includes('productDescription') ? { getProductDescription: product => product.description || '' }
      : name.includes('productEligibility') ? eligibilityModule.exports
      : { __esModule: true, default: name },
    ...globals,
  })
  return {
    render(props) { cursor = 0; effects = []; return module.exports.default(props) },
    retailer(props) { cursor = 0; effects = []; return module.exports.RetailerPicks(props) },
    flush() { for (const effect of effects) effect() },
  }
}

function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return undefined
  if (Array.isArray(tree)) {
    for (const child of tree) { const found = find(child, predicate); if (found) return found }
    return undefined
  }
  if (predicate(tree)) return tree
  return find(tree.props?.children, predicate)
}

test('App updates refined results and restores Home or New search after rendering', () => {
  for (const [callback, destination] of [['onHome', 'home'], ['onBack', 'search']]) {
    const scrolls = [], hashes = []
    const app = harness('App.jsx', {
      window: { cancelSmoothScroll() {}, history: { replaceState: (_, __, hash) => hashes.push(hash) } },
      document: { getElementById: id => ({ scrollIntoView: () => scrolls.push(id) }) },
    })
    let tree = app.render()
    find(tree, n => n.type === './SearchSection.jsx').props.onResults({ query: 'MacBook Air', products: [] })
    tree = app.render()
    const refined = { query: 'MacBook Air; under $1200', products: [] }
    find(tree, n => n.type === './SearchResults.jsx').props.onRefined(refined)
    tree = app.render()
    assert.equal(find(tree, n => n.type === './SearchResults.jsx').props.search, refined)
    find(tree, n => n.type === './Navbar.jsx').props[callback]()
    tree = app.render()
    assert.ok(find(tree, n => n.type === './SearchSection.jsx'))
    assert.equal(find(tree, n => n.type === './SearchResults.jsx'), undefined)
    app.flush()
    assert.equal(scrolls.at(-1), destination)
    assert.equal(hashes.at(-1), `#${destination}`)
  }
})

test('sequential refinements retain original intent and replace previous result arrays', async () => {
  const queries = []
  let search = { query: 'macbook', products: [{ title: 'Previous MacBook', price: 1299 }] }
  const results = harness('SearchResults.jsx', {
    fetch: async (_, options) => {
      const query = JSON.parse(options.body).query
      queries.push(query)
      return { ok: true, json: async () => ({ products: [{ title: 'MacBook', price: queries.length === 1 ? 999 : 799 }] }) }
    },
  })
  for (const detail of ['less than 1200', 'less than 900']) {
    const props = { search, onRefined: value => { search = value } }
    let tree = results.render(props)
    find(tree, n => n.props?.id === 'follow-up-search').props.onChange({ target: { value: detail } })
    tree = results.render(props)
    await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
  }
  assert.deepEqual(queries, ['macbook; less than 1200', 'macbook; less than 1200; less than 900'])
  assert.equal(search.products.length, 1)
  assert.equal(search.products[0].price, 799)
})

test('homepage filters stale collections and retailer responses and preserves full product data', async () => {
  const good = { title: 'Unknown ZX100', category: 'other', price: '99', currency: 'USD',
    description: 'Full description '.repeat(30), product_url: 'https://www.bestbuy.com/product/test/TEST',
    image_url: 'https://example.com/image.png', source: 'bestbuy.com', scraped_at: '2026-11-13T12:00:00Z',
    regular_price: '120', savings_percent: 17.5 }
  const mug = { ...good, title: 'Ceramic Mug', category: 'electronics' }
  const globals = {
    AbortController,
    fetch: async () => ({ ok: true, headers: { get: () => 'application/json' }, json: async () => ({
      collections: ['all-time-lows', 'bestbuy-picks'].map(id => ({ id, products: [mug, good] })),
      products: [mug, good],
    }) }),
  }
  const deals = harness('DealsSection.jsx', globals)
  deals.render()
  deals.flush()
  await new Promise(setImmediate)
  let tree = deals.render()
  const picks = find(tree, n => typeof n.type === 'function' && n.type.name === 'RetailerPicks')
  assert.equal(picks.props.initialProducts.length, 1)
  assert.equal(picks.props.initialProducts[0], good)
  assert.ok(!JSON.stringify(tree).includes('Ceramic Mug'))
  find(tree, n => n.type === 'button' && n.props['aria-label'] === `Preview ${good.title}`).props.onClick()
  tree = deals.render()
  const dialog = find(tree, n => n.props?.role === 'dialog')
  assert.ok(JSON.stringify(dialog).includes(good.description))
  assert.ok(JSON.stringify(dialog).includes(good.product_url))

  // Exercise the real retailer form without exporting a production-only test API.
  const retailer = harness('DealsSection.jsx', globals, '\nexport { RetailerPicks };')
  const props = { retailer: 'Best Buy', endpoint: '/api/bestbuy-search', initialProducts: [mug, good], homepageLoading: false, onPreview() {} }
  tree = retailer.retailer(props)
  assert.ok(!JSON.stringify(tree).includes('Ceramic Mug'))
  await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
  tree = retailer.retailer(props)
  assert.ok(!JSON.stringify(tree).includes('Ceramic Mug'))
  assert.ok(JSON.stringify(tree).includes(good.title))
})

test('header uses the supplied proportional dark logo and favicon is configured', () => {
  const navbar = harness('Navbar.jsx')
  const tree = navbar.render({ onHome() {} })
  const logo = find(tree, n => n.type === 'img')
  assert.equal(logo.props.src, '/branding/shoppie-logo-primary-dark-bg.svg')
  assert.equal(logo.props.className, 'h-9 w-auto')
  assert.ok(fs.readFileSync(`${__dirname}/../index.html`, 'utf8').includes('/branding/shoppie-favicon.svg'))
})

test('logo, header Home, drawer Home and New search invoke navigation callbacks', () => {
  let homes = 0, searches = 0, prevented = 0
  const navbar = harness('Navbar.jsx', { window: { cancelSmoothScroll() {} } })
  const tree = navbar.render({ isShowingResults: true, onHome: () => homes++, onBack: () => searches++ })
  const event = { preventDefault: () => prevented++ }
  find(tree, n => n.props?.['aria-label'] === 'Shoppie home').props.onClick(event)
  find(tree, n => n.type === 'a' && n.props.children[0] === 'Home').props.onClick(event)
  const drawer = find(tree, n => n.type === 'nav')
  find(drawer, n => n.type === 'a' && n.props.children[0] === 'Home').props.onClick(event)
  find(drawer, n => n.type === 'a' && n.props.children[0] === 'New search').props.onClick(event)
  assert.equal(homes, 3)
  assert.equal(searches, 1)
  assert.equal(prevented, 4)
})

test('refinement sends accumulated query and applies the response through onRefined', async () => {
  let request, updated
  const results = harness('SearchResults.jsx', {
    fetch: async (_, options) => {
      request = JSON.parse(options.body)
      return { ok: true, json: async () => ({ products: [{ title: 'MacBook Air' }], collection: { result_source: 'live' } }) }
    },
  })
  const props = {
    search: { query: 'MacBook Air; under $1200', products: [] },
    onRefined: value => { updated = value },
  }
  let tree = results.render(props)
  find(tree, n => n.props?.id === 'follow-up-search').props.onChange({ target: { value: 'less than 900 dollars' } })
  tree = results.render(props)
  await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
  assert.equal(request.query, 'MacBook Air; under $1200; less than 900 dollars')
  assert.equal(updated.query, request.query)
  assert.equal(updated.products[0].title, 'MacBook Air')
})
