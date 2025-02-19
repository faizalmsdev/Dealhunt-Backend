from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import os
import time
import re
import subprocess
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Install Chrome & ChromeDriver
def install_dependencies():
    logger.info("Installing system dependencies...")
    os.system("apt-get update")
    os.system("apt-get install -y wget curl unzip libnss3 libgconf-2-4 libxi6 libgbm1")
    logger.info("System dependencies installed.")

def install_chrome():
    logger.info("Installing Google Chrome...")
    os.system("wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
    os.system("dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install")
    logger.info("Google Chrome installed.")

def install_chromedriver():
    logger.info("Installing ChromeDriver...")
    chrome_version = subprocess.getoutput("google-chrome --version").split()[-1]
    chromedriver_url = f"https://chromedriver.storage.googleapis.com/{chrome_version}/chromedriver_linux64.zip"
    
    os.system(f"wget -q {chromedriver_url} -O chromedriver.zip")
    os.system("unzip -o chromedriver.zip -d /usr/local/bin/")
    os.system("chmod +x /usr/local/bin/chromedriver")
    logger.info("ChromeDriver installed.")

# Ensure everything is installed before starting
install_dependencies()
install_chrome()
install_chromedriver()

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    service = Service("/usr/local/bin/chromedriver")  # Use Service() instead of executable_path
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def clean_text(text):
    if not text:
        return ""
    return ' '.join(text.strip().split())

def extract_price(price_text):
    if not price_text:
        return ""
    match = re.search(r'₹\s*(\d+(?:\.\d{2})?)', price_text)
    return f"₹{match.group(1)}" if match else price_text.strip()

def safe_get_attribute(element, attribute, default=""):
    try:
        return element.get_attribute(attribute) if element else default
    except:
        return default

def scrape_zepto(driver, product_name):
    logger.info("Scraping Zepto...")
    products = []
    try:
        url = f"https://www.zeptonow.com/search?query={product_name.replace(' ', '+')}"
        driver.get(url)
        
        # Wait for products to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="product-card"]')))
        
        # Let the page fully load
        time.sleep(3)
        
        products_html = driver.find_elements(By.CSS_SELECTOR, '[data-testid="product-card"]')
        
        for product in products_html:  # Limit to 5 products for faster response
            try:
                html = product.get_attribute('outerHTML')
                soup = BeautifulSoup(html, 'html.parser')
                
                name = clean_text(soup.select_one('[data-testid="product-card-name"]').text if soup.select_one('[data-testid="product-card-name"]') else "")
                image = soup.select_one('img[data-testid="product-card-image"]')
                image_url = image['src'] if image else ""
                
                quantity = clean_text(soup.select_one('[data-testid="product-card-quantity"]').text if soup.select_one('[data-testid="product-card-quantity"]') else "")
                
                price_elem = soup.select_one('[data-testid="product-card-price"]')
                discounted_price = extract_price(price_elem.text if price_elem else "")
                
                original_price_elem = soup.select_one('p.line-through')
                original_price = extract_price(original_price_elem.text if original_price_elem else "")
                
                if name:  # Only add if we found a name
                    products.append({
                        "product_name": name,
                        "brand": name.split()[0],
                        "image_url": image_url,
                        "platforms": [{
                            "platform_image": "https://qcsearch.s3.ap-south-1.amazonaws.com/platforms/zepto.webp",
                            "name": "Zepto",
                            "navigation_url": url,
                            "original_price": original_price,
                            "discounted_price": discounted_price,
                            "quantity": quantity,
                            "delivery_time": "10 Mins",
                            "stock_status": "In Stock"
                        }]
                    })
            except Exception as e:
                logger.error(f"Error processing Zepto product: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error scraping Zepto: {str(e)}")
    
    return products

def scrape_swiggy(driver, product_name):
    logger.info("Scraping Swiggy Instamart...")
    products = []
    try:
        url = f"https://www.swiggy.com/instamart/search?query={product_name.replace(' ', '+')}"
        driver.get(url)
        
        # Wait for products to load
        time.sleep(5)  # Increased wait time for Swiggy
        
        products_html = driver.find_elements(By.CSS_SELECTOR, '[data-testid="default_container_ux4"]')
        
        for product in products_html:  # Limit to 5 products for faster response
            try:
                html = product.get_attribute('outerHTML')
                soup = BeautifulSoup(html, 'html.parser')
                
                name = clean_text(soup.select_one('.novMV').text if soup.select_one('.novMV') else "")
                image = soup.select_one('img.sc-dcJsrY')
                image_url = image['src'] if image else ""
                
                quantity = clean_text(soup.select_one('.sc-aXZVg.entQHA').text if soup.select_one('.sc-aXZVg.entQHA') else "")
                
                price_elem = soup.select_one('.sc-aXZVg.jLtxeJ')
                price = extract_price(price_elem.text if price_elem else "")
                
                delivery_time = clean_text(soup.select_one('.sc-aXZVg.giKYGQ').text if soup.select_one('.sc-aXZVg.giKYGQ') else "")
                
                if name:  # Only add if we found a name
                    products.append({
                        "product_name": name,
                        "brand": name.split()[0],
                        "image_url": image_url,
                        "platforms": [{
                            "platform_image": "https://qcsearch.s3.ap-south-1.amazonaws.com/platforms/swiggy.webp",
                            "name": "Swiggy",
                            "navigation_url": url,
                            "original_price": "",
                            "discounted_price": price,
                            "quantity": quantity,
                            "delivery_time": delivery_time,
                            "stock_status": "In Stock"
                        }]
                    })
            except Exception as e:
                logger.error(f"Error processing Swiggy product: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error scraping Swiggy: {str(e)}")
    
    return products

def scrape_blinkit(driver, product_name):
    logger.info("Scraping Blinkit...")
    products = []
    try:
        url = f"https://blinkit.com/s/?q={product_name.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load
        time.sleep(5)
        
        products_html = driver.find_elements(By.CSS_SELECTOR, '[data-test-id="plp-product"]')
        
        for product in products_html:  # Limit to 5 products for faster response
            try:
                html = product.get_attribute('outerHTML')
                soup = BeautifulSoup(html, 'html.parser')
                
                name = clean_text(soup.select_one('.Product__UpdatedTitle-sc-11dk8zk-9').text if soup.select_one('.Product__UpdatedTitle-sc-11dk8zk-9') else "")
                image = soup.select_one('.Imagestyles__ImageContainer-sc-1u3ccmn-0 img')
                image_url = image['src'] if image else ""
                
                quantity = clean_text(soup.select_one('.plp-product__quantity--box').text if soup.select_one('.plp-product__quantity--box') else "")
                
                original_price = extract_price(soup.select_one('div[style*="text-decoration-line: line-through"]').text if soup.select_one('div[style*="text-decoration-line: line-through"]') else "")
                discounted_price = extract_price(soup.select_one('div[style*="color: rgb(31, 31, 31)"]').text if soup.select_one('div[style*="color: rgb(31, 31, 31)"]') else "")
                
                delivery_time = clean_text(soup.select_one('div[style*="text-transform: uppercase"]').text if soup.select_one('div[style*="text-transform: uppercase"]') else "")
                
                if name:  # Only add if we found a name
                    products.append({
                        "product_name": name,
                        "brand": name.split()[0],
                        "image_url": image_url,
                        "platforms": [{
                            "platform_image": "https://qcsearch.s3.ap-south-1.amazonaws.com/platforms/blinkit.webp",
                            "name": "Blinkit",
                            "navigation_url": url,
                            "original_price": original_price,
                            "discounted_price": discounted_price,
                            "quantity": quantity,
                            "delivery_time": delivery_time,
                            "stock_status": "In Stock"
                        }]
                    })
            except Exception as e:
                logger.error(f"Error processing Blinkit product: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error scraping Blinkit: {str(e)}")
    
    return products

def merge_products(all_products):
    merged = {}

    for product in all_products:
        name = product["product_name"].lower()
        
        # If product name is already in the merged dictionary, add platform details
        if name in merged:
            merged[name]["platforms"].extend(product["platforms"])
        else:
            # Add the product as a new entry
            merged[name] = product
    
    # Convert dictionary back to list
    return list(merged.values())

@app.route('/search', methods=['POST'])
def search_products():
    try:
        data = request.json
        product_name = data.get('query', '')
        
        if not product_name:
            return jsonify({'error': 'No query provided'}), 400
            
        logger.info(f"Searching for: {product_name}")
        
        driver = setup_driver()
        try:
            # Scrape from all platforms (run in parallel in production)
            zepto_products = scrape_zepto(driver, product_name)
            swiggy_products = scrape_swiggy(driver, product_name)
            blinkit_products = scrape_blinkit(driver, product_name)
            
            # Combine all products
            all_products = zepto_products + swiggy_products + blinkit_products
            
            # Optional: Merge products with same name across platforms
            merged_products = merge_products(all_products)
            
            return jsonify(all_products)
            
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            driver.quit()
            
    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)