function SearchSection() {
  return (
    <section className="bg-blue-mist px-6 py-20 text-navy sm:py-28" aria-labelledby="search-heading">
      <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
        <div className="mb-6 grid size-24 place-items-center rounded-full border-2 border-dashed border-navy/25 bg-blue-mist text-5xl" role="img" aria-label="Placeholder mascot logo">
          🙂
        </div>
        <h2 id="search-heading" className="text-3xl font-semibold tracking-tight sm:text-4xl">What are you looking for?</h2>
        <p className="mt-3 max-w-lg text-base leading-7 text-navy/65">
          Search for a product to start comparing prices.
        </p>
        <form className="mt-8 flex w-full flex-col gap-3 rounded-2xl border border-navy/10 bg-white p-2 shadow-lg shadow-navy/5 sm:flex-row" role="search" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="product-search" className="sr-only">Search products</label>
          <input
            id="product-search"
            name="query"
            type="search"
            placeholder="Try “laptop” or “coffee maker”"
            className="min-w-0 flex-1 rounded-xl px-4 py-3 text-base text-navy outline-none placeholder:text-navy/40 focus-visible:ring-2 focus-visible:ring-blue-500"
          />
          <button type="submit" className="rounded-xl bg-navy px-7 py-3 font-semibold text-white transition hover:bg-navy-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy">
            Search
          </button>
        </form>
      </div>
    </section>
  )
}

export default SearchSection
