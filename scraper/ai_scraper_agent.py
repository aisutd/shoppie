# ai_scraper_agent.py
import json
import ollama
from playwright.sync_api import sync_playwright
from embeddings import generate_product_embedding
from scraper import fetch_rendered_page, extract_product
from database import connect, upsert_product
from scraper.config import DatabaseConfig

def universal_retailer_scraper(target_url: str) -> dict:
    """
    Uses the advanced scraper module to fetch and extract structured product data.
    """
    print(f"Scraper activated for URL: {target_url}")
    try:
        # Fetch rendered page using scraper.py capabilities
        html = fetch_rendered_page(target_url)
        product_record = extract_product(html, target_url)
        
        if not product_record or not product_record.get("title"):
            return {"error": "Failed to extract product record."}
            
        print(f"Successfully scraped: {product_record['title']}")
        return product_record
        
    except Exception as e:
        print(f"Scraper error encountered: {e}")
        return {"error": str(e)}

# Registry of available tools for the agent
tools_registry = {
    "universal_retailer_scraper": universal_retailer_scraper
}

def run_ecommerce_agent(user_goal: str):
    """
    Orchestrates the local LLM agent loop, handling tool calls,
    vector embedding generation, and final recommendation synthesis.
    """
    print(f"Agent started with goal: {user_goal}")
    print("-" * 60)

    tools_definition = [{
        'type': 'function',
        'function': {
            'name': 'universal_retailer_scraper',
            'description': 'Scrapes any e-commerce product web page to extract raw text, pricing, and specifications.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'target_url': {
                        'type': 'string',
                        'description': 'The exact full URL of the product page to scrape.',
                    },
                },
                'required': ['target_url'],
            },
        },
    }]

    messages = [{'role': 'user', 'content': user_goal}]

    # Execute up to 5 reasoning steps in the agent loop
    for step in range(5):
        response = ollama.chat(
            model='qwen2.5',
            messages=messages,
            tools=tools_definition,
        )

        message = response.get('message', {})
        
        # Check if the model decided to invoke a tool call
        if message.get('tool_calls'):
            messages.append(message)
            
            for tool in message['tool_calls']:
                fn_name = tool['function']['name']
                fn_args = tool['function']['arguments']
                
                print(f"Step {step + 1}: Executing tool '{fn_name}'")
                
                if fn_name in tools_registry:
                    scraped_product = tools_registry[fn_name](**fn_args)
                    
                    if scraped_product:
                        # Generate the 384-dimensional embedding using SBERT
                        vector_embedding = generate_product_embedding(scraped_product)
                        scraped_product['embedding_dimensions'] = len(vector_embedding)
                        tool_output = json.dumps(scraped_product)
                    else:
                        tool_output = "Error: Failed to extract product data."
                else:
                    tool_output = f"Error: Tool {fn_name} not found."

                # Feed the tool execution results back into conversation history
                messages.append({
                    'role': 'tool',
                    'content': tool_output,
                })
        else:
            # Final text response synthesis from the local LLM
            final_answer = message.get('content', '')
            output_file = "scraped_report.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(final_answer)

            print("-" * 60)
            print("Agent finished successfully.")
            print(f"Final report saved to: {output_file}")
            print("-" * 60)
            return final_answer

    return "Agent reached maximum steps without completion."

if __name__ == "__main__":
    goal = "Go to https://www.python.org and analyze its content structure."
    run_ecommerce_agent(goal)