from scraper import fetch_rendered_page, extract_product

# Use your direct Target product SKU link
test_url = "https://www.target.com/p/apple-macbook-neo-a18-pro-2026-laptop-256gb-blush/-/A-91122045"

print("Testing curl_cffi scraper module on Walmart...")
try:
    # Call fetch_rendered_page, which runs the curl_cffi implementation in scraper.py
    html = fetch_rendered_page(test_url)
    
    # Extract structured product fields using your existing JSON-LD / HTML extractors
    product = extract_product(html, test_url)
    
    print("\nScraping Successful!")
    print(f"Title: {product.get('title')}")
    print(f"Price: {product.get('price')} {product.get('currency')}")
    print(f"Availability: {product.get('availability')}")
    print(f"Seller: {product.get('seller')}")
    
except Exception as e:
    print(f"Scraper test failed: {e}")