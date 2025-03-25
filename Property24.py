import requests
from bs4 import BeautifulSoup
import pandas as pd  # Import pandas to work with data frames

# URL of properties for sale in Durban
url = "https://www.property24.com/for-sale/durban/kwazulu-natal/169"

# Set headers to mimic a real browser
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Send a GET request to fetch the webpage content
response = requests.get(url, headers=headers)

# Initialize a list to store the scraped data
property_list = []

# Check if the response was successful
if response.status_code == 200:
    soup = BeautifulSoup(response.content, "html.parser")

    # Find all property containers
    property_tiles = soup.find_all("div", class_="p24_regularTile")

    if not property_tiles:
        print("No properties found. Verify the structure and class names.")

    for prop in property_tiles:
        # Extract price
        price_tag = prop.find("span", class_="p24_price")
        price = price_tag.text.strip() if price_tag else "No Price"

        # Extract location
        location_tag = prop.find("span", class_="p24_location")
        location = location_tag.text.strip() if location_tag else "No Location"

        # Extract property title or description
        title_tag = prop.find("span", class_="p24_title")
        title = title_tag.text.strip() if title_tag else "No Title"

        # Extract number of bedrooms, bathrooms, parking, and size
        bedrooms = prop.find("span", title="Bedrooms")
        bathrooms = prop.find("span", title="Bathrooms")
        parking = prop.find("span", title="Parking Spaces")
        size_tag = prop.find("span", class_="p24_size")

        bedrooms = bedrooms.find_next("span").text.strip() if bedrooms else "No Bedrooms"
        bathrooms = bathrooms.find_next("span").text.strip() if bathrooms else "No Bathrooms"
        parking = parking.find_next("span").text.strip() if parking else "No Parking"
        size = size_tag.text.strip() if size_tag else "No Size"

        # Store the scraped data in a dictionary
        property_data = {
            "Title": title,
            "Price": price,
            "Location": location,
            "Bedrooms": bedrooms,
            "Bathrooms": bathrooms,
            "Parking": parking,
            "Size": size
        }

        # Add the property data to the list
        property_list.append(property_data)

else:
    print(f"Failed to retrieve data. HTTP Status Code: {response.status_code}")

# Convert the list of dictionaries into a pandas DataFrame
df = pd.DataFrame(property_list)

# Save the DataFrame to an Excel file
df.to_excel("property_listings.xlsx", index=False, engine="openpyxl")

print("Data has been saved to 'property_listings.xlsx'")
