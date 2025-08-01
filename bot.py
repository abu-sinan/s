import json
import random
import time
import requests
import logging
import sys
import os
from io import StringIO
from playwright.sync_api import sync_playwright
from datetime import datetime

class TelegramLogger:
    def __init__(self, bot, log_level=logging.INFO):
        self.bot = bot
        self.log_level = log_level
        self.terminal = sys.stdout
        
    def write(self, message):
        self.terminal.write(message)
        if message.strip():
            if self.log_level == logging.ERROR and any(
                word in message.lower() 
                for word in ['error', 'fail', 'exception', 'traceback']
            ):
                self.bot.send_telegram(f"🚨 Terminal Error:\n```\n{message.strip()}\n```")
            elif self.log_level == logging.INFO:
                self.bot.send_telegram(f"ℹ️ Terminal Output:\n```\n{message.strip()}\n```")
                
    def flush(self):
        self.terminal.flush()

class PopMartBot:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.telegram_enabled = 'telegram' in self.config
        self.setup_logging()
        logging.info("🤖 Bot initialized")

    def load_config(self, config_path):
        """Load and validate configuration file"""
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = ['email', 'password', 'products']
            if not all(field in config for field in required_fields):
                raise ValueError(f"Missing required fields in config: {required_fields}")
            
            return config
        except Exception as e:
            logging.error(f"Failed to load config: {str(e)}")
            raise

    def setup_logging(self):
        """Configure logging system"""
        sys.stdout = TelegramLogger(self, logging.INFO)
        sys.stderr = TelegramLogger(self, logging.ERROR)
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def send_telegram(self, message, photo_path=None):
        """Send notification via Telegram"""
        if not self.telegram_enabled:
            return
            
        try:
            url = f"https://api.telegram.org/bot{self.config['telegram']['token']}/sendMessage"
            payload = {
                "chat_id": self.config['telegram']['chat_id'],
                "text": f"🧸 PopMart Bot:\n{message}",
                "parse_mode": "Markdown"
            }
            
            if photo_path:
                url = f"https://api.telegram.org/bot{self.config['telegram']['token']}/sendPhoto"
                with open(photo_path, 'rb') as photo:
                    requests.post(
                        url,
                        files={'photo': photo},
                        data={"chat_id": self.config['telegram']['chat_id'], "caption": message},
                        timeout=10
                    )
            else:
                requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram notification failed: {str(e)}")

    def random_delay(self, min=1.0, max=3.0):
        """Human-like random delay"""
        delay = random.uniform(min, max)
        time.sleep(delay)
        logging.debug(f"Delay: {delay:.2f}s")

    def debug_screenshot(self, name):
        """Capture debug screenshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"debug_{name}_{timestamp}.png"
        self.page.screenshot(path=path)
        return path

    def apply_stealth(self):
        """Apply anti-detection measures"""
        stealth_js = """
        delete Object.getPrototypeOf(navigator).webdriver;
        window.navigator.chrome = {
            runtime: {},
            app: { isInstalled: false },
            webstore: { onInstallStageChanged: {}, onDownloadProgress: {} },
            csi: function() {},
            loadTimes: function() {},
        };
        Object.defineProperty(navigator, 'plugins', {
            get: () => [{
                name: 'Chrome PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
            }],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });
        """
        try:
            self.page.add_init_script(script=stealth_js)
            logging.info("🕵️ Stealth mode activated")
        except Exception as e:
            logging.error(f"Stealth injection failed: {str(e)}")
            raise

    def handle_cloudflare(self):
        """Handle Cloudflare challenges"""
        max_wait = 120  # Maximum wait time in seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # Check for different Cloudflare challenge types
                if self.page.locator("div#challenge-stage").count() > 0:
                    logging.info("⏳ Cloudflare verification detected (Challenge Stage)")
                    self.page.wait_for_selector("div#challenge-stage", state="hidden", timeout=30000)
                    return True
                
                if self.page.locator('text="Verify you are human"').count() > 0:
                    logging.info("⏳ Cloudflare human verification detected")
                    debug_img = self.debug_screenshot("cloudflare_challenge")
                    self.send_telegram("⚠️ Manual intervention needed: Cloudflare human verification required", debug_img)
                    return False
                
                if self.page.locator('text="Checking your browser"').count() > 0:
                    logging.info("⏳ Cloudflare browser check detected")
                    self.page.wait_for_selector('text="Checking your browser"', state="hidden", timeout=30000)
                    return True
                
                # If no challenge detected but page isn't loading
                if time.time() - start_time > 30:
                    if self.page.locator("body").count() == 0:
                        raise Exception("Page failed to load")
                    return True
                    
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Cloudflare handling error: {str(e)}")
                self.debug_screenshot("cloudflare_error")
                raise

        raise Exception("Cloudflare verification timeout")

    def login(self):
        """Login with Cloudflare handling"""
        max_retries = 3
        login_url = "https://www.popmart.com/us/user/login?redirect=%2Faccount"
        
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"🔐 Login attempt {attempt}/{max_retries}")
                
                # Navigate to login page
                self.page.goto(login_url, timeout=60000)
                
                # Handle Cloudflare
                if not self.handle_cloudflare():
                    raise Exception("Cloudflare verification failed")
                
                # Fill email
                email_field = self.page.locator('input#email, input[placeholder*="e-mail"]')
                email_field.wait_for(timeout=30000)
                email_field.fill(self.config["email"])
                self.random_delay(1, 2)
                
                # Check terms box if exists
                terms_checkbox = self.page.locator('input[type="checkbox"]').first
                if terms_checkbox.count() > 0:
                    terms_checkbox.check()
                    self.random_delay(1, 2)
                
                # Click continue
                continue_btn = self.page.locator('button:has-text("CONTINUE")')
                continue_btn.click(timeout=30000)
                
                # Handle Cloudflare again
                self.handle_cloudflare()
                
                # Fill password
                password_field = self.page.locator('input#password, input[placeholder*="password"]')
                password_field.wait_for(timeout=30000)
                password_field.fill(self.config["password"])
                self.random_delay(1, 2)
                
                # Click sign in
                signin_btn = self.page.locator('button:has-text("SIGN IN")')
                signin_btn.click(timeout=30000)
                
                # Verify login success
                try:
                    self.page.wait_for_selector('img[alt*="Profile"], div.account-page', timeout=30000)
                    logging.info("🔑 Login successful")
                    return True
                except:
                    error_msg = self.page.locator('div.ant-message-error, div.error-message')
                    if error_msg.count() > 0:
                        raise Exception(f"Login error: {error_msg.inner_text(timeout=5000)}")
                    raise Exception("Login verification timeout")
                    
            except Exception as e:
                debug_img = self.debug_screenshot(f"login_fail_attempt_{attempt}")
                self.send_telegram(f"⚠️ Login attempt {attempt} failed: {str(e)}", debug_img)
                
                if attempt < max_retries:
                    retry_delay = 10 * attempt  # Exponential backoff
                    logging.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    self.page.reload()
                    continue
                
                raise Exception(f"Login failed after {max_retries} attempts")

    def launch_browser(self):
        """Configure browser with anti-detection settings"""
        return self.playwright.chromium.launch(
            headless=False,  # Required for Cloudflare
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ],
            timeout=60000
        )

    def create_context(self):
        """Create browser context with stealth settings"""
        return self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            permissions=["geolocation"],
            storage_state="auth.json" if os.path.exists("auth.json") else None
        )

    def process_product(self, product):
        """Handle product purchase flow"""
        try:
            logging.info(f"🔍 Checking: {product['name']}")
            self.page.goto(product["url"], timeout=60000)
            
            # Check stock
            if self.page.locator('button:has-text("SOLD OUT")').count() > 0:
                logging.warning(f"⛔ Out of stock: {product['name']}")
                return False
                
            # Select size
            size_locator = f'div.index_sizeInfoTitle__kpZbS:has-text("{product["size"]}")'
            self.page.locator(size_locator).click(timeout=10000)
            
            # Set quantity
            for _ in range(product["quantity"] - 1):
                self.page.locator('div.index_countButton__mJU5Q').last.click()
                self.random_delay(0.2, 0.5)
            
            # Add to cart
            self.page.locator('div.index_usBtn__2KIEx:has-text("ADD TO BAG")').click(timeout=10000)
            logging.info(f"🛒 Added to cart: {product['name']}")
            
            # View bag
            self.page.locator('button:has-text("View Bag")').click(timeout=10000)
            return True
            
        except Exception as e:
            debug_img = self.debug_screenshot(f"product_fail_{product['name']}")
            self.send_telegram(f"❌ Failed processing {product['name']}: {str(e)}", debug_img)
            return False

    def monitor_products(self):
        """Main monitoring loop"""
        try:
            # Initialize Playwright
            self.playwright = sync_playwright().start()
            self.browser = self.launch_browser()
            self.context = self.create_context()
            self.page = self.context.new_page()
            
            # Apply stealth and navigate
            self.apply_stealth()
            self.page.goto("https://www.popmart.com/us", timeout=60000)
            self.handle_cloudflare()
            
            # Login with retries
            if not self.login():
                self.send_telegram("🔴 Critical: Cannot proceed without login")
                return
                
            # Save authentication state
            self.context.storage_state(path="auth.json")
            
            # Main monitoring loop
            while True:
                for product in self.config["products"]:
                    try:
                        self.process_product(product)
                    except Exception as e:
                        logging.error(f"Product processing failed: {str(e)}")
                        continue
                    self.random_delay(3, 5)  # Delay between products
                
                logging.info(f"♻️ Cycle complete. Next in {self.config['scan_interval']}s")
                time.sleep(self.config["scan_interval"])
                
        except KeyboardInterrupt:
            logging.info("🛑 Bot stopped by user")
        except Exception as e:
            logging.critical(f"💀 Fatal error: {str(e)}", exc_info=True)
            raise
        finally:
            # Cleanup resources
            if hasattr(self, 'page') and self.page:
                self.page.close()
            if hasattr(self, 'context') and self.context:
                self.context.close()
            if hasattr(self, 'browser') and self.browser:
                self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                self.playwright.stop()
            logging.info("🔴 Bot stopped")

if __name__ == "__main__":
    bot = PopMartBot("config.json")
    bot.monitor_products()