from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re
import time
from selenium.webdriver.chrome.options import Options

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Railway-specific Chrome binary path
    chrome_options.binary_location = os.getenv("GOOGLE_CHROME_BIN", "/usr/bin/google-chrome")
    
    # Use the ChromeDriver path from environment variable
    chrome_driver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
    service = Service(executable_path=chrome_driver_path)
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Failed to create driver: {str(e)}")
        raise

# Rest of your scraping functions remain the same
def clean_text(text):
    if not text:
        return ""
    return ' '.join(text.strip().split())

def extract_price(price_text):
    if not price_text:
        return ""
    match = re.search(r'₹\s*(\d+(?:\.\d{2})?)', price_text)
    return f"₹{match.group(1)}" if match else price_text.strip()

# Your existing scraping functions (scrape_zepto, scrape_swiggy, scrape_blinkit) remain unchanged

def merge_products(all_products):
    merged = {}
    for product in all_products:
        name = product["product_name"].lower()
        if name in merged:
            merged[name]["platforms"].extend(product["platforms"])
        else:
            merged[name] = product
    return list(merged.values())

@app.route('/search', methods=['POST'])
def search_products():
    try:
        data = request.json
        product_name = data.get('query', '')
        
        if not product_name:
            return jsonify({'error': 'No query provided'}), 400
            
        logger.info(f"Searching for: {product_name}")
        
        try:
            driver = setup_driver()
            # Scrape from all platforms
            zepto_products = scrape_zepto(driver, product_name)
            swiggy_products = scrape_swiggy(driver, product_name)
            blinkit_products = scrape_blinkit(driver, product_name)
            
            all_products = zepto_products + swiggy_products + blinkit_products
            merged_products = merge_products(all_products)
            
            return jsonify(merged_products)
            
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            if 'driver' in locals():
                driver.quit()
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)