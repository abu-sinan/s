import json
import logging
import sys
import requests
import http.client
import urllib3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# Suppress requests debug output
http.client.HTTPConnection.debuglevel = 0
urllib3.disable_warnings()
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Custom logging handler to send messages to Telegram
class TelegramHandler(logging.Handler):
    def __init__(self, bot_token, chat_id):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id

    def emit(self, record):
        log_entry = self.format(record)
        try:
            self.send_telegram_message(log_entry)
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")

    def send_telegram_message(self, message):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message
        }
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")

# Load configuration from config.json
def load_config():
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config

# Set up logging with console and Telegram handlers
def setup_logging(bot_token, chat_id):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels
    logger.handlers.clear()

    # Console handler for all output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Telegram handler for INFO and above
    telegram_handler = TelegramHandler(bot_token, chat_id)
    telegram_handler.setLevel(logging.INFO)  # Only INFO, WARNING, ERROR
    telegram_handler.setFormatter(formatter)
    logger.addHandler(telegram_handler)

# Main bot function
def run_bot():
    # Load config and set up logging
    config = load_config()
    setup_logging(config['telegram']['bot_token'], config['telegram']['chat_id'])

    # Initialize Chrome WebDriver
    driver = webdriver.Chrome()
    driver.maximize_window()

    try:
        # Step 1: Navigate to Pop Mart website
        driver.get("https://www.popmart.com")
        logging.info("Navigated to Pop Mart website.")

        # Step 2: Handle location selection
        try:
            location_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'United States')]"))
            )
            location_button.click()
            logging.info("Location set to United States.")
        except:
            logging.warning("Location selection not required or already set.")

        # Step 3: Accept policy consent
        try:
            accept_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'ACCEPT')]"))
            )
            accept_button.click()
            logging.info("Policy consent accepted.")
        except:
            logging.warning("Policy consent not found or already accepted.")

        # Step 4: Log in
        try:
            driver.get("https://www.popmart.com/login")  # Adjust URL if needed
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.send_keys(config['email'])

            password_input = driver.find_element(By.ID, "password")
            password_input.send_keys(config['password'])

            # Assuming a terms checkbox exists
            checkbox = driver.find_element(By.CLASS_NAME, "index_serviceCheckbox_KjCPj")
            checkbox.click()

            continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
            continue_button.click()
            logging.info("Logged in successfully.")
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            raise

        # Step 5: Navigate to product page
        driver.get(config['product_url'])
        logging.info("Navigated to product page.")

        # Step 6: Select size and quantity
        try:
            # Assuming size is a dropdown (adjust locator if needed)
            size_select = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "size"))
            )
            select = Select(size_select)
            select.select_by_visible_text(config['size'])

            # Assuming quantity is an input field
            quantity_input = driver.find_element(By.XPATH, "//input[@type='number']")
            quantity_input.clear()
            quantity_input.send_keys(str(config['quantity']))
            logging.info(f"Selected size {config['size']} and quantity {config['quantity']}.")
        except Exception as e:
            logging.error(f"Failed to select size and quantity: {str(e)}")
            raise

        # Step 7: Add to cart
        try:
            add_to_cart_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to Cart')]"))
            )
            add_to_cart_button.click()
            logging.info("Item added to cart.")
        except Exception as e:
            logging.error(f"Failed to add to cart: {str(e)}")
            raise

        # Step 8: View cart
        try:
            view_cart_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View Bag')]"))
            )
            view_cart_button.click()
            logging.info("Cart viewed.")
        except Exception as e:
            logging.error(f"Failed to view cart: {str(e)}")
            raise

        # Step 9: Proceed to checkout
        try:
            checkout_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CHECK OUT')]"))
            )
            checkout_button.click()
            logging.info("Proceeding to checkout.")
        except Exception as e:
            logging.error(f"Failed to proceed to checkout: {str(e)}")
            raise

        # Step 10: Complete purchase (simulated)
        logging.info("Payment step reached. (Purchase simulation complete)")

    except Exception as e:
        logging.error(f"Bot encountered an error: {str(e)}")
    finally:
        driver.quit()
        logging.info("Browser closed.")

# Run the bot
if __name__ == "__main__":
    run_bot()