import json
import os
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- Tottus Scraper Functions (Asynchronous with Playwright) ---

async def get_tottus_data_from_page(page, url):
    """
    Navigates to a URL using Playwright, waits for network idle,
    and extracts the __NEXT_DATA__ JSON from the HTML.
    """
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        
        soup = BeautifulSoup(html, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
        
        if script_tag:
            if script_tag.string:
                print(f"__NEXT_DATA__ script found and has content on {url}.")
                return json.loads(script_tag.string)
            else:
                print(f"__NEXT_DATA__ script found on {url} but its content is empty.")
                return None
        else:
            print(f"No __NEXT_DATA__ script found on {url}")
            # Optionally, save the HTML to a file for manual inspection
            # with open("debug_tottus_page.html", "w", encoding="utf-8") as f:
            #     f.write(html)
            # print("Saved current page HTML to debug_tottus_page.html for inspection.")
            return None
    except Exception as e:
        print(f"Error fetching data from {url}: {e}")
        return None

async def get_tottus_categories_async():
    """
    Fetches Tottus categories by navigating to the main page
    and extracting category links from the __NEXT_DATA__ JSON.
    """
    async with async_playwright() as p:
        # Launch browser in non-headless mode for debugging
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CL"
        )
        page = await context.new_page()
        
        print("Fetching Tottus categories...")
        data = await get_tottus_data_from_page(page, "https://www.tottus.cl/tottus-cl")
        await browser.close()

        if not data:
            print("Failed to retrieve Tottus categories data.")
            return []

        print(f"Keys in __NEXT_DATA__ for categories: {data.keys()}") # Debug print

        # Parse the JSON for top-level category links
        # Path: data['props']['pageProps']['page']['containers'][20]['components'][18]['data']['cards']
        categories = []
        try:
            # Safely get nested dictionary values
            cards = data.get('props', {}).get('pageProps', {}).get('page', {}).get('containers', [])
            
            # Find the correct container and component
            target_component = None
            for container in cards:
                if isinstance(container, dict) and 'components' in container:
                    for component in container['components']:
                        if isinstance(component, dict) and component.get('data', {}).get('cards') is not None:
                            # This is a heuristic. We're looking for a component that has 'data' and 'cards' within it.
                            # The original path was very specific [20]['components'][18].
                            # Let's try to be more flexible.
                            # If the original path is consistently correct, you can revert to:
                            # cards_data = data['props']['pageProps']['page']['containers'][20]['components'][18]['data']['cards']
                            
                            # For now, let's assume the cards are directly under 'data'
                            if 'cards' in component['data']:
                                target_component = component['data']['cards']
                                break
                if target_component:
                    break

            if target_component:
                for card in target_component:
                    link = card.get('link')
                    if link and isinstance(link, str) and link.startswith('/'):
                        categories.append(link)
            else:
                print("Could not find the 'cards' data at the expected or an alternative path for categories.")

        except KeyError as e:
            print(f"Could not find Tottus category links at expected path: {e}")
            return []
        except Exception as e:
            print(f"An error occurred while parsing Tottus categories: {e}")
            return []
        
        return categories

async def get_tottus_products_by_category_async(category_url_path):
    """
    Fetches products for a specific Tottus category, iterating through pages
    using Playwright and extracting slugs from __NEXT_DATA__.
    """
    all_product_slugs = []
    page_num = 1
    base_url = "https://www.tottus.cl"
    
    async with async_playwright() as p:
        # Launch browser in non-headless mode for debugging
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="es-CL"
        )
        page = await context.new_page()

        print(f"--- Fetching Tottus products for category: {category_url_path} ---")

        while True:
            current_product_list_url = f"{base_url}{category_url_path}?page={page_num}&store=to_com"
            print(f"Accessing: {current_product_list_url}")
            
            data = await get_tottus_data_from_page(page, current_product_list_url)
            
            if not data:
                print(f"No data retrieved for {category_url_path} page {page_num}. Ending pagination.")
                break

            products = []
            try:
                # --- Updated JSON path for Tottus products ---
                # Path: data['props']['pageProps']['results']
                results = data.get('props', {}).get('pageProps', {}).get('results')
                if isinstance(results, list):
                    products = results
                else:
                    print(f"Expected 'results' to be a list, but got {type(results)} for {category_url_path} page {page_num}.")
                    break # End pagination if results are not as expected

            except Exception as e:
                print(f"Error parsing Tottus products from __NEXT_DATA__ for {category_url_path} page {page_num}: {e}")
                break # End pagination on parsing error

            if not products:
                print(f"No products extracted for {category_url_path} page {page_num}.")
                break # No products, end pagination

            initial_slug_count = len(all_product_slugs)
            for product in products:
                # Extract 'url' instead of 'slug' as per the new requirement
                product_url = product.get("url")
                if product_url and isinstance(product_url, str):
                    all_product_slugs.append(product_url)
            
            if len(all_product_slugs) == initial_slug_count:
                print(f"No new Tottus products found on page {page_num} for {category_url_path}. Ending pagination.")
                break # No new products, end pagination

            page_num += 1
            await asyncio.sleep(1) # Be polite and avoid hammering the server

        await browser.close()
    return all_product_slugs

async def run_tottus_scraper():
    """Main function to run the Tottus scraper."""
    print("Starting Tottus scraper...")
    categories = await get_tottus_categories_async()
    if not categories:
        print("No Tottus categories found. Exiting Tottus scraper.")
        return

    print(f"Found {len(categories)} Tottus category URLs.")
    # print(categories) # Uncomment to see the list of extracted category URLs

    all_product_slugs = []

    for category_url_path in categories:
        # Example category_url_path: /tottus-cl/lista/CATG27055/Despensa
        slugs = await get_tottus_products_by_category_async(category_url_path)
        all_product_slugs.extend(slugs)
        print(f"Finished processing Tottus category URL: {category_url_path}. Total slugs collected so far: {len(all_product_slugs)}")

    unique_slugs = sorted(list(set(all_product_slugs)))
    print(f"\n--- Tottus Product Slugs Collected ---")
    print(f"Total unique Tottus product slugs found across all categories: {len(unique_slugs)}") 

    output_filename = "tottus_product_urls.txt" # Changed filename to reflect URLs
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            for url in unique_slugs: # Iterate through URLs
                f.write(url + '\n')
        print(f"Successfully saved {len(unique_slugs)} unique Tottus product URLs to '{output_filename}'")
        current_directory = os.getcwd()
        full_path = os.path.join(current_directory, output_filename)
        print(f"You can find the file at: {full_path}")
    except IOError as e:
        print(f"Error saving Tottus URLs to file '{output_filename}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving the Tottus file: {e}")

# --- Main Execution ---

async def main():
    """
    Main entry point for running the supermarket scrapers.
    Currently set to run only the Tottus scraper.
    """
    await run_tottus_scraper()

if __name__ == "__main__":
    # Ensure playwright browsers are installed:
    # You might need to run `playwright install` in your terminal if you haven't already.
    # This command needs to be run once in your environment.
    # `playwright install`
    asyncio.run(main())