from sentence_transformers import SentenceTransformer

# Initialize the lightweight, high-performance SBERT model
model = SentenceTransformer('all-MiniLM-L6-v2')

def generate_product_embedding(product: dict) -> list:
    """
    Combines key product fields into a single text representation and generates
    a 384-dimensional vector using sentence-transformers.
    """
    title = product.get('title', '')
    brand = product.get('brand', '')
    category = product.get('category', '')
    description = product.get('description', '')

    combined_text = f"Title: {title} | Brand: {brand} | Category: {category} | Description: {description}"
    
    # Encode text into a float list vector
    embedding = model.encode(combined_text)
    return embedding.tolist()