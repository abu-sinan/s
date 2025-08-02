import time
import logging
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from undetected_chromedriver import Chrome, ChromeOptions
import cloudscraper
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PRODUCT_URLS = [
    "https://www.popmart.com/us/products/1584/LABUBU-%C3%97-PRONOUNCE---WINGS-OF-FORTUNE-Vinyl-Plush-Hanging-Card",
    "https://www.popmart.com/us/products/1921/HACIPUPU-Snuggle-With-You-Series-Plush-Bag-Blind-Box"
]
LOGIN_URL = "https://www.popmart.com/us/user/login?redirect=%2Faccount"
USERNAME = "abusinan1523@gmail.com"
PASSWORD = "your_password"  # Replace with your password
PROXY = None  # Replace with "http://user:pass@host:port" if using proxies
CHECK_INTERVAL = 5  # Seconds between checks
MAX_ATTEMPTS = 100  # Max monitoring attempts per product
MAX_RETRY_OOPS = 3  # Max retries for "Oops" error
CHROME_BINARY_PATH = "/usr/bin/google-chrome"  # Chrome binary path in Codespaces

# Selectors from provided HTML
SELECTOR_LOCATION_POPUP = "div.index_ipWarnContainer__d5qTd"
SELECTOR_UPDATE_LOCATION = "div.index_chooseCountry__EjEl9"
SELECTOR_POLICY_ACCEPT = "div.policy_acceptBtn__ZNU71"
SELECTOR_EMAIL = "input#email"
SELECTOR_CHECKBOX_TERMS = "input.ant-checkbox-input"
SELECTOR_CONTINUE_BUTTON = "button.index_loginButton__O6r8l"
SELECTOR_PASSWORD = "input#password"
SELECTOR_SIGN_IN_BUTTON = "button.index_loginButton__O6r8l[type='submit']"
SELECTOR_SIZE_SINGLE = "div.index_sizeInfoItem__f_Uxb.index_active__CP2n5"  # Single box
SELECTOR_QUANTITY_PLUS = "div.index_countButton__mJU5Q:not(.index_disableBtn__cDpGw)"
SELECTOR_ADD_TO_BAG = "div.index_usBtn__2KlEx.index_red__kx6Ql"
SELECTOR_ADDED_NOTIFICATION = "div.ant-notification-notice-message"
SELECTOR_VIEW_BAG = "button.index_noticeFooterBtn__XpFsc:not(.index_btnBorder__xieC3)"
SELECTOR_SELECT_ALL = "div.index_selectText___HDXz"
SELECTOR_CHECKOUT = "button.index_checkout__V9YPC"
SELECTOR_PROCEED_TO_PAY = "button.index_placeOrderBtn__wgYr6"
SELECTOR_CREDIT_CARD = "div.index_leftActivity__sbIxm"
SELECTOR_PAY_BUTTON = "button.adyen-checkout__button--pay"
SELECTOR_OOPS_MODAL = "div.ant-modal-content"
SELECTOR_OOPS_OK = "button.layout_wafErrorModalButton__yJdyc"
SELECTOR_CLOUDFLARE_MESSAGE = "div.ant-message"

def setup_driver():
    """Set up undetected Chrome driver with proxy and user-agent rotation."""
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(f"user-agent={random_user_agent()}")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.binary_location = CHROME_BINARY_PATH  # Explicitly set Chrome binary
    
    if PROXY:
        chrome_options.add_argument(f"--proxy-server={PROXY}")
    
    try:
        driver = Chrome(options=chrome_options, headless=False)  # Set headless=True for no UI
        driver.set_page_load_timeout(30)
        logger.info("Chrome driver initialized successfully.")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome driver: {e}")
        raise

def random_user_agent():
    """Return a random user-agent to avoid detection."""
    user_agents = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    ]
    return random.choice(user_agents)

def bypass_cloudflare(driver, session, url):
    """Check for Cloudflare verification and wait if present."""
    try:
        response = session.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        if "cf-browser-verification" in response.text or response.status_code == 403:
            logger.warning("Cloudflare verification detected. Waiting for browser to resolve...")
            WebDriverWait(driver, 30).until_not(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_CLOUDFLARE_MESSAGE)))
            logger.info("Cloudflare verification passed.")
            return False
        return True
    except Exception as e:
        logger.error(f"Cloudflare check error: {e}")
        return False

def handle_popups(driver):
    """Handle location and policy acceptance pop-ups."""
    try:
        # Handle United States location pop-up
        if len(driver.find_elements(By.CSS_SELECTOR, SELECTOR_LOCATION_POPUP)) > 0:
            logger.info("Handling location pop-up...")
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_UPDATE_LOCATION)))
            driver.find_element(By.CSS_SELECTOR, SELECTOR_UPDATE_LOCATION).click()
        
        # Handle policy acceptance
        if len(driver.find_elements(By.CSS_SELECTOR, SELECTOR_POLICY_ACCEPT)) > 0:
            logger.info("Accepting policy...")
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_POLICY_ACCEPT)))
            driver.find_element(By.CSS_SELECTOR, SELECTOR_POLICY_ACCEPT).click()
    except Exception as e:
        logger.error(f"Pop-up handling error: {e}")

def login(driver):
    """Log in to Pop Mart account."""
    try:
        logger.info("Navigating to login page...")
        driver.get(LOGIN_URL)
        handle_popups(driver)
        
        # Enter email
        logger.info("Entering email...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_EMAIL)))
        driver.find_element(By.CSS_SELECTOR, SELECTOR_EMAIL).send_keys(USERNAME)
        
        # Check terms checkbox
        logger.info("Checking terms checkbox...")
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CHECKBOX_TERMS)))
        driver.find_element(By.CSS_SELECTOR, SELECTOR_CHECKBOX_TERMS).click()
        
        # Click Continue
        logger.info("Clicking continue...")
        driver.find_element(By.CSS_SELECTOR, SELECTOR_CONTINUE_BUTTON).click()
        
        # Enter password and sign in
        logger.info("Entering password...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_PASSWORD)))
        driver.find_element(By.CSS_SELECTOR, SELECTOR_PASSWORD).send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, SELECTOR_SIGN_IN_BUTTON).click()
        
        WebDriverWait(driver, 15).until(EC.url_contains("account") or EC.presence_of_element_located((By.CSS_SELECTOR, "a.account-link")))
        logger.info("Logged in successfully.")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise

def monitor_product(driver, session, product_url):
    """Monitor product availability and trigger purchase."""
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        logger.info(f"Monitoring {product_url} - Attempt {attempts}/{MAX_ATTEMPTS}")
        
        # Check for Cloudflare block
        if not bypass_cloudflare(driver, session, product_url):
            logger.warning("Waiting for Cloudflare verification...")
            time.sleep(random.uniform(3, 7))
            continue
        
        try:
            driver.get(product_url)
            handle_popups(driver)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_ADD_TO_BAG)))
            
            # Select Single box (if applicable)
            single_box = driver.find_elements(By.CSS_SELECTOR, SELECTOR_SIZE_SINGLE)
            if single_box and "index_active__CP2n5" not in single_box[0].get_attribute("class"):
                logger.info("Selecting Single box...")
                driver.execute_script("arguments[0].click();", single_box[0])
            
            # Set quantity (e.g., 1; adjust if needed)
            quantity_plus = driver.find_elements(By.CSS_SELECTOR, SELECTOR_QUANTITY_PLUS)
            if quantity_plus and False:  # Change False to True to increase quantity
                logger.info("Setting quantity to 2...")
                driver.execute_script("arguments[0].click();", quantity_plus[0])  # Click + for quantity=2
            
            # Check if Add to Bag is enabled
            add_to_bag = driver.find_element(By.CSS_SELECTOR, SELECTOR_ADD_TO_BAG)
            if add_to_bag.is_enabled():
                logger.info("Product in stock! Attempting purchase...")
                purchase_product(driver)
                return True
            else:
                logger.info("Add to Bag button disabled. Retrying...")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        
        time.sleep(random.uniform(CHECK_INTERVAL, CHECK_INTERVAL + 3))
    
    logger.error(f"Max attempts reached for {product_url}. Product not found.")
    return False

def purchase_product(driver):
    """Execute purchase process."""
    retry_count = 0
    while retry_count < MAX_RETRY_OOPS:
        try:
            # Click Add to Bag
            logger.info("Adding to bag...")
            add_to_bag = driver.find_element(By.CSS_SELECTOR, SELECTOR_ADD_TO_BAG)
            driver.execute_script("arguments[0].click();", add_to_bag)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTOR_ADDED_NOTIFICATION)))
            
            # Click View Bag
            logger.info("Viewing bag...")
            view_bag = driver.find_element(By.CSS_SELECTOR, SELECTOR_VIEW_BAG)
            driver.execute_script("arguments[0].click();", view_bag)
            
            # Select All
            logger.info("Selecting all items...")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_SELECT_ALL)))
            driver.find_element(By.CSS_SELECTOR, SELECTOR_SELECT_ALL).click()
            
            # Click Checkout
            logger.info("Proceeding to checkout...")
            checkout = driver.find_element(By.CSS_SELECTOR, SELECTOR_CHECKOUT)
            driver.execute_script("arguments[0].click();", checkout)
            
            # Proceed to Pay
            logger.info("Proceeding to payment...")
            WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_PROCEED_TO_PAY)))
            driver.find_element(By.CSS_SELECTOR, SELECTOR_PROCEED_TO_PAY).click()
            
            # Select Credit Card
            logger.info("Selecting credit card...")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_CREDIT_CARD)))
            driver.find_element(By.CSS_SELECTOR, SELECTOR_CREDIT_CARD).click()
            
            # Click Pay
            logger.info("Completing payment...")
            pay_button = driver.find_element(By.CSS_SELECTOR, SELECTOR_PAY_BUTTON)
            driver.execute_script("arguments[0].click();", pay_button)
            
            WebDriverWait(driver, 15).until(EC.url_contains("thank-you") or EC.presence_of_element_located((By.CSS_SELECTOR, "div.order-confirmation")))
            logger.info("Purchase successful!")
            return True
        except Exception as e:
            # Check for "Oops" modal
            if len(driver.find_elements(By.CSS_SELECTOR, SELECTOR_OOPS_MODAL)) > 0:
                logger.warning("High order volume error detected. Retrying...")
                driver.find_element(By.CSS_SELECTOR, SELECTOR_OOPS_OK).click()
                retry_count += 1
                time.sleep(random.uniform(2, 5))
                continue
            logger.error(f"Purchase failed: {e}")
            raise
    
    logger.error("Max retries reached for Oops error.")
    return False

def main():
    """Main function to run the bot."""
    session = cloudscraper.create_scraper()
    driver = None
    try:
        logger.info("Starting bot...")
        driver = setup_driver()
        login(driver)
        
        # Monitor each product URL
        for product_url in PRODUCT_URLS:
            if monitor_product(driver, session, product_url):
                logger.info(f"Successfully purchased product from {product_url}")
                break
        else:
            logger.error("No products were available after checking all URLs.")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        if driver:
            logger.info("Closing browser...")
            driver.quit()
        session.close()

if __name__ == "__main__":
    main()