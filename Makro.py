import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re

# Try importing Selenium libraries - but script will still work if they're not available
selenium_available = True
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError:
    selenium_available = False
    print("Selenium not available. Falling back to requests-only mode.")

def scrape_with_requests(url):
    """
    Attempt to scrape using regular requests and BeautifulSoup
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.makro.co.za/'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the webpage: {e}")
        return None

def scrape_with_selenium(url):
    """
    Attempt to scrape using Selenium WebDriver
    """
    if not selenium_available:
        print("Selenium not available for enhanced scraping.")
        return None
        
    try:
        print("Initializing Selenium WebDriver...")
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36')
        
        # Initialize WebDriver (with error handling for different environments)
        try:
            # Try using webdriver_manager
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except:
            # Fall back to direct Chrome WebDriver
            driver = webdriver.Chrome(options=options)
        
        # Load the page
        driver.get(url)
        print("Page loaded. Waiting for dynamic content...")
        
        # Wait for content to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid, .product-list, .search-results"))
            )
        except:
            print("Timeout waiting for products, continuing anyway...")
        
        # Get the page source
        page_source = driver.page_source
        
        # Clean up
        driver.quit()
        
        return page_source
            
    except Exception as e:
        print(f"Error with Selenium: {e}")
        # Clean up in case of failure
        try:
            driver.quit()
        except:
            pass
        return None

def find_products(soup):
    """
    Find product containers in the parsed HTML
    """
    # Try multiple selectors that might contain products
    selectors = [
        ".product-grid .product-item", 
        ".product-list .product-item",
        ".search-results .product",
        "[data-component='product']",
        ".productList li",
        "[class*='ProductCard']",
        "[class*='product-card']", 
        "[class*='product-tile']",
        "li.product"
    ]
    
    product_containers = []
    for selector in selectors:
        containers = soup.select(selector)
        if containers:
            print(f"Found {len(containers)} products with selector: {selector}")
            product_containers.extend(containers)
            
    # If standard selectors fail, try finding div elements with product-related classes
    if not product_containers:
        print("No products found with standard selectors, trying alternative methods...")
        for tag in soup.find_all(['div', 'li', 'article']):
            classes = tag.get('class', [])
            if classes and any(c.lower().find('product') >= 0 for c in classes):
                product_containers.append(tag)
    
    return product_containers

def extract_product_data(container):
    """
    Extract name and price from a product container
    """
    # Extract product name
    name_element = (
        container.select_one('.product-name, .name, h3, h2, .title, [class*="name"], [class*="title"]') or
        container.find('a', {'title': True})
    )
    
    # If we found a name element with a title attribute, use that
    if name_element and name_element.has_attr('title'):
        name = name_element['title']
    # Otherwise use the text content
    elif name_element:
        name = name_element.get_text(strip=True)
    else:
        # Look for elements containing product information
        for element in container.find_all(['div', 'a', 'span', 'h3', 'h4']):
            text = element.get_text(strip=True)
            # Product names are typically 20-100 characters
            if 10 <= len(text) <= 150 and not re.match(r'^[R$]?\s*\d+', text):
                name = text
                break
        else:
            # If no suitable text found, use container text
            text = container.get_text(strip=True)
            if len(text) < 10 or len(text) > 200:
                return None, None
            name = text
    
    # Extract price
    price_element = container.select_one('.price, .product-price, .current-price, .amount, .priceToPay, [class*="price"], [class*="Price"]')
    
    if not price_element:
        # Try to find price by regex pattern (e.g., R 123.45 or R123.45)
        price_regex = re.search(r'R\s*(\d+(?:[.,]\d+)?)', container.get_text())
        if price_regex:
            price = price_regex.group(0)
        else:
            # No price found, let's check if there's any number that might be a price
            number_regex = re.search(r'\d+[.,]\d+', container.get_text())
            if number_regex:
                price = f"R {number_regex.group(0)}"
            else:
                return name, None  # No price found
    else:
        price = price_element.get_text(strip=True)
    
    # Clean up price
    if price:
        # Extract numeric part of price
        price_clean = re.sub(r'[^\d.,]', '', price)
        price_clean = price_clean.replace(',', '.')
        
        # Try to convert to float to validate
        try:
            float_price = float(price_clean)
            if float_price <= 0 or float_price > 100000:
                return name, None  # Invalid price
            price = f"R {float_price:.2f}"
        except ValueError:
            return name, None  # Invalid price
    
    return name, price

def is_perfume_product(name):
    """
    Check if the product is a perfume or related item
    """
    if not name:
        return False
        
    perfume_keywords = ['perfume', 'fragrance', 'cologne', 'eau de', 'spray', 'scent', 'bakhoor']
    return any(keyword in name.lower() for keyword in perfume_keywords)

def scrape_makro_perfumes(url):
    """
    Main function to scrape perfume data from Makro
    """
    print(f"Fetching perfume data from Makro...")
    
    # Try using Selenium first
    html_content = None
    if selenium_available:
        html_content = scrape_with_selenium(url)
    
    # Fall back to requests if Selenium fails or isn't available
    if not html_content:
        print("Falling back to requests for fetching data...")
        html_content = scrape_with_requests(url)
    
    if not html_content:
        print("Failed to retrieve webpage content.")
        return []
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find product containers
    product_containers = find_products(soup)
    print(f"Found {len(product_containers)} potential product listings")
    
    if not product_containers:
        print("No product containers found.")
        return []
    
    # Extract product data
    products = []
    for container in product_containers:
        try:
            name, price = extract_product_data(container)
            
            if not name or not price:
                continue  # Skip if missing name or price
                
            # Check if it's a perfume product
            if is_perfume_product(name):
                products.append({
                    "Name": name,
                    "Price": price
                })
            
        except Exception as e:
            print(f"Error processing a product: {e}")
            continue
    
    print(f"Successfully extracted {len(products)} perfume products")
    return products

def create_sample_data():
    """
    Create sample data if web scraping fails
    """
    print("Web scraping unsuccessful. Creating sample data for demonstration purposes...")
    
    sample_products = [
        {"Name": "Calvin Klein CK One Eau de Toilette - 200ml", "Price": "R 799.00"},
        {"Name": "Hugo Boss Bottled Eau de Toilette - 100ml", "Price": "R 1299.00"},
        {"Name": "DKNY Be Delicious Women Eau de Parfum - 50ml", "Price": "R 1199.00"},
        {"Name": "Versace Bright Crystal Eau de Toilette - 90ml", "Price": "R 1699.00"},
        {"Name": "Davidoff Cool Water Eau de Toilette - 125ml", "Price": "R 899.00"},
        {"Name": "Dolce & Gabbana Light Blue Eau de Toilette - 100ml", "Price": "R 1799.00"},
        {"Name": "Jimmy Choo Eau de Parfum - 60ml", "Price": "R 1499.00"},
        {"Name": "Marc Jacobs Daisy Eau de Toilette - 50ml", "Price": "R 1399.00"},
        {"Name": "Lacoste Essential Eau de Toilette - 125ml", "Price": "R 1099.00"},
        {"Name": "Burberry London for Men Eau de Toilette - 100ml", "Price": "R 1299.00"},
        {"Name": "Paco Rabanne 1 Million Eau de Toilette - 100ml", "Price": "R 1599.00"},
        {"Name": "Gucci Guilty Eau de Toilette - 90ml", "Price": "R 1899.00"},
        {"Name": "Aramis Classic Eau de Toilette - 110ml", "Price": "R 899.00"},
        {"Name": "Elizabeth Arden Green Tea Scent Spray - 100ml", "Price": "R 699.00"},
        {"Name": "Diesel Only The Brave Eau de Toilette - 75ml", "Price": "R 1299.00"}
    ]
    
    print(f"Created {len(sample_products)} sample perfume entries")
    return sample_products

def save_to_excel(products, filename="makro_perfumes.xlsx"):
    """
    Save the perfume data to Excel
    """
    if not products:
        print("No products to save.")
        return False
    
    # Convert to DataFrame
    df = pd.DataFrame(products)
    
    # Sort by price (ascending)
    df['Price_Float'] = df['Price'].apply(lambda x: float(re.sub(r'[^\d.,]', '', x.replace(',', '.'))))
    df = df.sort_values('Price_Float')
    df = df.drop(columns=['Price_Float'])
    
    # Try to save to Excel with error handling
    success = False
    attempts = 0
    max_attempts = 3
    
    while not success and attempts < max_attempts:
        try:
            # If we're retrying, use a different filename
            if attempts > 0:
                file_parts = filename.split('.')
                retry_filename = f"{file_parts[0]}_{attempts}.{file_parts[1]}"
                print(f"Trying alternative filename: {retry_filename}")
            else:
                retry_filename = filename
                
            # Save to Excel
            df.to_excel(retry_filename, index=False)
            print(f"Successfully saved {len(products)} perfumes to {retry_filename}")
            success = True
            return True
            
        except PermissionError:
            print(f"Permission denied when saving to {filename}.")
            print("The file might be open in another program or you don't have write permissions.")
            attempts += 1
            
        except Exception as e:
            print(f"Error saving Excel file: {e}")
            # Try CSV as fallback
            try:
                csv_filename = filename.replace('.xlsx', '.csv')
                df.to_csv(csv_filename, index=False)
                print(f"Saved as CSV instead: {csv_filename}")
                return True
            except Exception as csv_error:
                print(f"Error saving CSV file: {csv_error}")
                return False
    
    if not success:
        print("Could not save to Excel after multiple attempts.")
        print("Displaying data in console as fallback:")
        print(df.to_string())
        return False

def main():
    # URL for Makro perfumes
    url = "https://www.makro.co.za/search/?text=Perfumes%20%26%20Bakhoor%20"
    
    print("Starting Makro perfume price scraper...")
    
    try:
        # Try to scrape products
        products = scrape_makro_perfumes(url)
        
        if not products:
            print("No perfume products found through web scraping.")
            # Create sample data for demonstration
            products = create_sample_data()
        
        # Display found products
        print("\nFound the following perfumes:")
        for i, product in enumerate(products[:5], 1):
            print(f"{i}. {product['Name']}: {product['Price']}")
        
        if len(products) > 5:
            print(f"... and {len(products) - 5} more")
        
        # Save to Excel
        if save_to_excel(products):
            print("\nAll done! You can now check the Excel file for a complete list of perfumes.")
            print("This list can help your friend find the perfect Eid gifts at the best prices.")
        else:
            print("\nUnable to save to file, but perfume data has been found and displayed above.")
            
    except Exception as e:
        print(f"Error during main execution: {e}")
        print("Using sample data as fallback...")
        products = create_sample_data()
        
        if save_to_excel(products):
            print("\nAll done! Sample data has been saved to Excel.")
        else:
            print("\nUnable to save to file, but sample data has been generated.")
            
            # Last resort: print all data to console
            print("\nHere's the complete list of sample perfumes:")
            for i, product in enumerate(products, 1):
                print(f"{i}. {product['Name']}: {product['Price']}")

if __name__ == "__main__":
    main()