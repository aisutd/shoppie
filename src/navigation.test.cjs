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
      if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value }]
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
      : name.includes('productDescription') ? { getProductDescription: product => product.description || '' }
      : name.includes('productEligibility') ? eligibilityModule.exports
      : name === './ProductCard.jsx' ? {
        __esModule: true, default: name, Price: 'Price', ProductArtwork: 'ProductArtwork',
        RetailerLabel: 'RetailerLabel', retailerName: product => product.source,
      }
      : { __esModule: true, default: name },
    ...globals,
  })
  return {
    render(props) { cursor = 0; effects = []; return module.exports.default(props) },
    renderExport(name, props) { cursor = 0; effects = []; return module.exports[name](props) },
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

function browserSession(start = '/') {
  const entries = [{ path: start, state: null }], storage = new Map()
  let index = 0
  let backOrForward
  const location = { pathname: start }
  return {
    document: {},
    window: {
      location, scrollTo() {},
      history: {
        get state() { return entries[index].state },
        pushState(state, _, path) {
          entries.splice(++index, entries.length, { path, state })
          location.pathname = path
        },
        replaceState(state, _, path) {
          entries[index] = { path, state }
          location.pathname = path
        },
        go(step) {
          index += step
          location.pathname = entries[index].path
          backOrForward()
        },
      },
      sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
      addEventListener(type, handler) { if (type === 'popstate') backOrForward = handler },
    },
  }
}

test('Home shows results without navigation and retains refinements across Discover and refresh', () => {
  const globals = browserSession()
  const { history, location } = globals.window
  const app = harness('App.jsx', globals)
  const component = (tree, name) => find(tree, n => n.type === `./${name}.jsx`)
  let tree = app.render()
  app.flush()
  find(tree, n => typeof n.type === 'function' && n.type.name === 'Home').props.onResults({ query: 'MacBook Air', products: [] })
  assert.equal(location.pathname, '/')
  tree = app.render()
  assert.equal(component(tree, 'SearchResults').props.isActive, true)
  const refined = { query: 'MacBook Air; under $1200', products: [] }
  component(tree, 'SearchResults').props.onRefined(refined)
  tree = app.render()
  assert.equal(component(tree, 'SearchResults').props.search, refined)
  component(tree, 'Navbar').props.navigate('/discover')
  tree = app.render()
  assert.equal(component(tree, 'DealsSection').props.isActive, true)
  assert.equal(component(tree, 'SearchResults').props.isActive, false)
  history.go(-1)
  tree = app.render()
  assert.equal(component(tree, 'SearchResults').props.search, refined)
  assert.equal(component(tree, 'DealsSection').props.isActive, false)
  history.go(1)
  tree = app.render()
  const refreshed = component(harness('App.jsx', globals).render(), 'SearchResults').props
  assert.equal(refreshed.search.query, refined.query)
  assert.equal(location.pathname, '/discover')
  const discover = component(app.render(), 'DealsSection').props.footer.props
  discover.navigate(discover.to)
  assert.equal(location.pathname, '/')
  assert.equal(component(app.render(), 'SearchResults').props.search, refined)
})

test('legacy Listings replaces the URL and keeps any saved search on Home', () => {
  for (const saved of [null, { query: 'Laptop', products: [] }]) {
    const globals = browserSession('/listings')
    if (saved) globals.window.sessionStorage.setItem('shoppie.search', JSON.stringify(saved))
    const app = harness('App.jsx', globals)
    const tree = app.render()
    app.flush()
    assert.equal(globals.window.location.pathname, '/')
    assert.ok(find(tree, n => typeof n.type === 'function' && n.type.name === 'Home').props.isActive)
    assert.equal(find(tree, n => n.type === './SearchResults.jsx')?.props.search.query, saved?.query)
  }
})

test('back links use explicit in-app destinations and normal anchor hrefs', () => {
  const links = harness('PageBackLink.jsx')
  const event = { button: 0 }
  for (const [to, label] of [['/', 'Home']]) {
    const tree = links.render({ to, navigate: (href, click) => {
      assert.equal(href, to)
      assert.equal(click, event)
    } })
    const link = find(tree, n => n.type === 'a')
    assert.equal(tree.type, 'footer')
    assert.equal(link.props.href, to)
    assert.match(link.props.children.slice(1).join(''), new RegExp(`Back to ${label}`))
    link.props.onClick(event)
  }
})

test('a late refinement cannot replace a newer Home search', () => {
  const globals = browserSession()
  const app = harness('App.jsx', globals)
  const home = tree => find(tree, n => typeof n.type === 'function' && n.type.name === 'Home')
  const results = tree => find(tree, n => n.type === './SearchResults.jsx')
  home(app.render()).props.onResults({ query: 'MacBook', products: [] })
  const first = results(app.render()).props
  first.onNewSearch()
  home(app.render()).props.onResults({ query: 'Sony headphones', products: [] })
  first.onRefined({ query: 'MacBook; under $1200', products: [] })
  assert.equal(results(app.render()).props.search.query, 'Sony headphones')
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

test('Discover shows four collections and preserves retailer searches and full product details', async () => {
  const good = { title: 'Unknown ZX100', category: 'other', price: '99', currency: 'USD',
    description: 'Full description '.repeat(30), product_url: 'https://www.bestbuy.com/product/test/TEST',
    image_url: 'https://example.com/image.png', source: 'bestbuy.com', scraped_at: '2026-11-13T12:00:00Z',
    regular_price: '120', savings_percent: 17.5, match_reason: 'Exact model match' }
  const mug = { ...good, title: 'Ceramic Mug', category: 'electronics' }
  const discountOnly = { ...good, title: 'Discount collection only', product_url: `${good.product_url}2` }
  const requests = []
  const globals = {
    AbortController,
    fetch: async (endpoint, options) => {
      requests.push([endpoint, options.method, options.body && JSON.parse(options.body).query])
      return { ok: true, headers: { get: () => 'application/json' }, json: async () => ({
        collections: [
          ...['all-time-lows', 'bestbuy-picks'].map(id => ({ id, products: [mug, good] })),
          { id: 'deep-discounts', products: [discountOnly] },
        ],
        products: [mug, good],
        discounts: [discountOnly],
      }) }
    },
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
  const tabs = find(tree, n => n.type === './CollectionPicker.jsx').props
  assert.deepEqual(Array.from(tabs.items, item => item.label), [
    'No Filters', 'Best Buy Picks', 'Walmart Picks', 'Lowest Current Prices', 'Recently Observed',
  ])
  assert.equal(tabs.selected, 'all')
  assert.equal(find(tree, n => n.props?.id === 'discover-panel-deep-discounts'), undefined)
  assert.ok(!JSON.stringify(tree).includes(discountOnly.title))
  const collections = tabs.items.slice(1)
  for (const selected of [tabs.items[0], ...collections, tabs.items[0]]) {
    tabs.onSelect(selected.id)
    const selectedTree = deals.render()
    for (const item of collections) {
      const panel = find(selectedTree, n => n.props?.id === `discover-panel-${item.id}`)
      assert.equal(panel.props.hidden, selected.id !== 'all' && selected.id !== item.id)
    }
  }
  assert.deepEqual(requests, [['/api/deals', undefined, undefined]])
  tabs.onSelect('all-time-lows')
  tree = deals.render()
  const rail = find(tree, n => typeof n.type === 'function' && n.type.name === 'ProductRail')
  assert.equal(rail.props.products[0], good)
  rail.props.onPreview(good)
  tree = deals.render()
  const details = find(tree, n => n.type === './ProductDetails.jsx')
  assert.equal(details.props.product, good)
  const dialog = harness('ProductDetails.jsx').render(details.props)
  assert.ok(JSON.stringify(dialog).includes(good.description))
  assert.ok(JSON.stringify(dialog).includes(good.product_url))
  assert.ok(JSON.stringify(dialog).includes(good.match_reason))
  assert.ok(JSON.stringify(dialog).includes(good.scraped_at))
  const price = harness('ProductCard.jsx').renderExport('Price', { product: good })
  assert.match(JSON.stringify(price), /\$99\.00.*\$120\.00.*17\.5/)

  // Exercise the real retailer form without exporting a production-only test API.
  for (const { retailer, endpoint } of tabs.items.filter(item => item.retailer)) {
    const component = harness('DealsSection.jsx', globals, '\nexport { RetailerPicks };')
    const props = { retailer, endpoint, initialProducts: [mug, good], homepageLoading: false, onPreview() {} }
    tree = component.renderExport('RetailerPicks', props)
    assert.ok(!JSON.stringify(tree).includes('Ceramic Mug'))
    const input = find(tree, n => n.type === 'input')
    assert.equal(input.props.value, '')
    assert.equal(input.props.placeholder, `Search ${retailer} products...`)
    const beforeSubmit = requests.length
    await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
    assert.equal(requests.length, beforeSubmit)
    input.props.onChange({ target: { value: '  ZX100  ' } })
    tree = component.renderExport('RetailerPicks', props)
    assert.equal(requests.length, beforeSubmit)
    await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
    tree = component.renderExport('RetailerPicks', props)
    assert.ok(!JSON.stringify(tree).includes('Ceramic Mug'))
    assert.ok(JSON.stringify(tree).includes(good.title))
    assert.ok(!JSON.stringify(tree).includes(discountOnly.title))
  }
  assert.deepEqual(requests, [
    ['/api/deals', undefined, undefined], ['/api/bestbuy-search', 'POST', 'ZX100'], ['/api/walmart-search', 'POST', 'ZX100'],
  ])
})

test('header uses the supplied proportional dark logo and favicon is configured', () => {
  const navbar = harness('Navbar.jsx')
  const tree = navbar.render({ onHome() {} })
  const logo = find(tree, n => n.type === 'img')
  assert.equal(logo.props.src, '/branding/shoppie-logo-primary-dark-bg.svg')
  assert.equal(logo.props.width, '203')
  assert.equal(logo.props.height, '56')
  assert.ok(fs.readFileSync(`${__dirname}/../index.html`, 'utf8').includes('/branding/shoppie-favicon.svg'))
})

test('logo and navigation expose only Home and Discover and mark the current page', () => {
  const paths = []
  const tree = harness('Navbar.jsx').render({ route: '/discover', navigate: path => paths.push(path) })
  const nav = find(tree, n => n.type === 'nav')
  for (const [label, href] of [['Home', '/'], ['Discover', '/discover']]) {
    const { props } = find(nav, n => n.type === 'a' && n.props.children[0] === label)
    assert.equal(props.href, href)
    assert.equal(props['aria-current'], href === '/discover' ? 'page' : undefined)
    props.onClick({})
  }
  find(tree, n => n.props?.['aria-label'] === 'Shoppie home').props.onClick({})
  assert.equal(find(nav, n => n.props?.href === '/listings'), undefined)
  assert.deepEqual(paths, ['/', '/discover', '/'])
})

test('Discover picker highlights the active option and closes on selection and Escape', () => {
  const picker = harness('CollectionPicker.jsx')
  const items = [{ id: 'first', label: 'First pick' }, { id: 'second', label: 'Second pick' }]
  let selected = 'first'
  const draw = () => picker.render({ items, selected, onSelect: value => { selected = value }, isActive: true })
  const trigger = tree => find(tree, n => n.props?.['aria-controls'] === 'discover-collections')
  let tree = draw()
  assert.equal(trigger(tree).props['aria-expanded'], false)
  trigger(tree).props.onClick()
  tree = draw()
  assert.equal(trigger(tree).props['aria-expanded'], true)
  assert.ok(find(tree, n => n.props?.['aria-pressed'] === true))
  tree.props.onKeyDown({ key: 'Escape', preventDefault() {} })
  assert.equal(trigger(draw()).props['aria-expanded'], false)
  trigger(draw()).props.onClick()
  find(draw(), n => n.props?.['aria-pressed'] === false).props.onClick()
  assert.equal(selected, 'second')
  assert.equal(trigger(draw()).props['aria-expanded'], false)
})

test('results show total matches separately from visible cards in each retailer group', () => {
  const results = harness('SearchResults.jsx')
  const products = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, source: i < 20 ? 'bestbuy.com' : 'walmart.com' }))
  const props = { search: { query: 'laptop', products, collection: { result_source: 'hybrid', live_matches: 3, catalog_matches: 22 } } }
  const grid = tree => find(tree, n => n.props?.className === 'listing-grid')
  const tabs = tree => find(tree, n => n.type === './Tabs.jsx').props
  const more = tree => find(tree, n => n.type === 'button' && n.props.children[0] === 'Load more')
  let tree = results.render(props)
  assert.equal(grid(tree).props.children[0].length, 12)
  assert.equal(tabs(tree).items[0].count, 25)
  more(tree).props.onClick()
  tree = results.render(props)
  assert.equal(grid(tree).props.children[0].length, 24)
  more(tree).props.onClick()
  tree = results.render(props)
  assert.equal(grid(tree).props.children[0].length, 25)
  tabs(tree).onSelect('walmart.com')
  tree = results.render(props)
  assert.equal(grid(tree).props.children[0].length, 5)
  assert.equal(tabs(tree).items.find(group => group.id === 'bestbuy.com').count, 20)
  assert.equal(products.length, 25)
})

test('Home search keeps its loading and error states and accepts a valid empty response', async () => {
  let finish, search, requests = 0
  const form = harness('SearchSection.jsx', { fetch: (endpoint, options) => {
    requests += 1
    assert.equal(endpoint, '/api/search')
    assert.equal(options.method, 'POST')
    assert.equal(JSON.parse(options.body).query, 'laptop')
    return new Promise(resolve => { finish = resolve })
  } })
  const draw = () => form.render({ onResults: value => { search = value } })
  const input = find(draw(), n => n.type === 'input')
  assert.equal(input.props.value, '')
  assert.equal(input.props.placeholder, 'Try "laptop" to find great tech deals')
  const submit = () => find(draw(), n => n.type === 'form').props.onSubmit({ preventDefault() {} })
  await submit()
  assert.equal(search, undefined)
  assert.equal(requests, 0)
  find(draw(), n => n.type === 'input').props.onChange({ target: { value: 'laptop' } })
  let request = submit()
  assert.ok(find(draw(), n => n.props?.role === 'status'))
  finish({ ok: false, json: async () => ({ error: 'Search timed out.' }) })
  await request
  assert.equal(find(draw(), n => n.props?.role === 'alert').props.children[0], 'Search timed out.')
  assert.equal(search, undefined)
  request = submit()
  finish({ ok: true, json: async () => ({ products: [], collection: { result_source: 'catalog' } }) })
  await request
  assert.equal(search.query, 'laptop')
  const empty = harness('SearchResults.jsx').render({ search })
  assert.ok(find(empty, n => n.type === 'h2' && n.props.children[0] === 'No matching products'))
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
