from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests  # For exchange rate
import pandas as pd  # For saving to Excel

# Setup Selenium WebDriver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode (no UI)
options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass bot detection
options.add_argument("--window-size=1920x1080")  # Set window size
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # Fake user-agent

# Initialize driver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Open Amazon search results page
search_query = "laptop"
url = f"https://www.amazon.com/s?k={search_query}"
driver.get(url)

# Wait for elements to load
time.sleep(5)

# Scroll down to load more products
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(3)

# Get the latest USD to ZAR exchange rate
try:
    response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
    exchange_rate = response.json()["rates"]["ZAR"]
except:
    exchange_rate = 18.50  # Fallback rate if API fails

# Extract product titles and prices
products = driver.find_elements(By.XPATH, '//div[@data-component-type="s-search-result"]')

data = []  # Store scraped data

if not products:
    print("No products found. Amazon may have blocked the request.")

for product in products[:10]:  # Get first 10 products
    try:
        title = product.find_element(By.XPATH, './/div[@data-cy="title-recipe"]//h2/span').text  # Fixed XPath
    except:
        title = "Title not found"

    try:
        price_whole = product.find_element(By.XPATH, './/span[contains(@class, "a-price-whole")]').text
        price_fraction = product.find_element(By.XPATH, './/span[contains(@class, "a-price-fraction")]').text
        price_usd = float(f"{price_whole}.{price_fraction}")  # Convert to float
        price_zar = round(price_usd * exchange_rate, 2)  # Convert to ZAR
        price_display = f"${price_usd} (~R{price_zar})"
    except:
        price_display = "Price not found"

    # Store data in list
    data.append([title, price_display])

# Close driver
driver.quit()

# Convert data to DataFrame
df = pd.DataFrame(data, columns=["Title", "Price (USD & ZAR)"])

# Save to Excel file
file_name = "Amazon_Products.xlsx"
df.to_excel(file_name, index=False)

print(f"✅ Data successfully saved to {file_name}")
