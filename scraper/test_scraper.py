from scraper import fetch_rendered_page, extract_product

#Tech product URLs for all 4 retailers
test_urls = {
    "Amazon": "https://www.amazon.com/dp/B0CX23V2ZK",
    "Walmart": "https://www.walmart.com/ip/Apple-15-inch-MacBook-Air-Apple-M5-nbsp-chip-w-10-core-CPU-10-core-GPU-512GB-SSD-16GB-RAM-Midnight-MDVH4LL-A-2026/19694602757",
    "Best Buy": "https://www.bestbuy.com/site/apple-macbook-air-13-inch-apple-m4-chip-built-for-apple-intelligence-16gb-memory-256gb-ssd-midnight/6565862.p",
    "Target": "https://www.target.com/p/apple-macbook-neo-a18-pro-2026-laptop-256gb-blush/-/A-91122045"
}

for retailer, url in test_urls.items():
    print(f"\n==========================================")
    print(f"Testing curl_cffi scraper on {retailer}...")
    print(f"==========================================")
    try:
        # Call fetch_rendered_page using curl_cffi
        html = fetch_rendered_page(url)
        
        if not html or len(html) < 500:
            print(f"Warning: Response was empty or too short ({len(html) if html else 0} bytes). Possible block.")
            continue
            
        # Extract structured product fields
        product = extract_product(html, url)
        
        print(f"Scraping Successful!")
        print(f"Title:        {product.get('title')}")
        print(f"Price:        {product.get('price')} {product.get('currency')}")
        print(f"Availability: {product.get('availability')}")
        print(f"Seller:       {product.get('seller')}")
        
    except Exception as e:
        print(f"Scraper test failed for {retailer}: {e}")