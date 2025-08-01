import json
import random
import time
import requests
import logging
import sys
from io import StringIO
from playwright.sync_api import sync_playwright
from datetime import datetime

class TelegramLogger:
    """Captures and forwards terminal output to Telegram"""
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

    def setup_logging(self):
        """Configure logging to capture all output"""
        sys.stdout = TelegramLogger(self, logging.INFO)
        sys.stderr = TelegramLogger(self, logging.ERROR)
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def load_config(self, path):
        """Load configuration with validation"""
        try:
            with open(path) as f:
                config = json.load(f)
                
            # Validate required fields
            if not all(k in config for k in ['email', 'password', 'products']):
                raise ValueError("Missing required config fields")
                
            return config
        except Exception as e:
            logging.error(f"Config load failed: {str(e)}")
            raise

    def send_telegram(self, message, photo_path=None):
        """Send notification with error handling"""
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
        """Human-like delay with jitter"""
        delay = random.uniform(min, max)
        time.sleep(delay)
        logging.debug(f"Delay: {delay:.2f}s")

    def apply_stealth(self):
        """Inject anti-detection scripts"""
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.navigator.chrome = { runtime: {}, app: { isInstalled: false } };
        """
        try:
            self.page.add_init_script(script=stealth_js)
            logging.info("🕵️ Stealth measures applied")
        except Exception as e:
            logging.error(f"Stealth injection failed: {str(e)}")
            raise

    def handle_cloudflare(self):
        """Wait for Cloudflare challenge"""
        if self.page.locator("div#challenge-stage").count() > 0:
            logging.info("⏳ Cloudflare verification detected")
            try:
                self.page.wait_for_selector("div#challenge-stage", state="hidden", timeout=120000)
                logging.info("✅ Cloudflare verification passed")
            except Exception as e:
                self.page.screenshot(path="cloudflare_failure.png")
                logging.error(f"Cloudflare timeout: {str(e)}")
                raise

    def debug_screenshot(self, name):
        """Capture debug screenshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"debug_{name}_{timestamp}.png"
        self.page.screenshot(path=path)
        return path

    def login(self):
        """Enhanced login with retries and debugging"""
        max_retries = self.config.get('login', {}).get('max_retries', 3)
        retry_delay = self.config.get('login', {}).get('retry_delay', 5)
        
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"🔐 Login attempt {attempt}/{max_retries}")
                
                # Navigate to login page
                login_btn = self.page.locator('a[href*="/user/login"]').first
                login_btn.click(timeout=15000)
                self.page.wait_for_load_state("networkidle", timeout=30000)
                
                # Fill email
                email_field = self.page.locator('input#email')
                email_field.wait_for(timeout=10000)
                email_field.fill(self.config["email"])
                
                # Accept terms if needed
                terms_checkbox = self.page.locator('input.ant-checkbox-input')
                if terms_checkbox.count() > 0:
                    terms_checkbox.check()
                
                # Click continue
                continue_btn = self.page.locator('button:has-text("CONTINUE")')
                continue_btn.click(timeout=15000)
                self.page.wait_for_load_state("networkidle", timeout=30000)
                
                # Fill password
                password_field = self.page.locator('input#password')
                password_field.wait_for(timeout=10000)
                password_field.fill(self.config["password"])
                
                # Submit login
                signin_btn = self.page.locator('button:has-text("SIGN IN")')
                signin_btn.click(timeout=15000)
                
                # Verify success
                try:
                    self.page.locator('img[alt*="Profile"]').wait_for(timeout=20000)
                    logging.info("🔑 Login successful")
                    return True
                except:
                    error_msg = self.page.locator('div.ant-message-error')
                    if error_msg.count() > 0:
                        raise Exception(f"Login error: {error_msg.inner_text()}")
                    raise Exception("Login timeout")
                    
            except Exception as e:
                debug_img = self.debug_screenshot(f"login_fail_attempt_{attempt}")
                self.send_telegram(f"⚠️ Login attempt {attempt} failed: {str(e)}", debug_img)
                
                if attempt < max_retries:
                    logging.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    self.page.reload()
                    continue
                
                raise Exception(f"Login failed after {max_retries} attempts")

    def launch_browser(self):
        """Configure browser instance"""
        return self.playwright.chromium.launch(
            headless=self.config.get("headless", True),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
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
            record_har_path="network.har" if self.config.get("debug", False) else None
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
                
            # Main monitoring loop
            while True:
                for product in self.config["products"]:
                    self.process_product(product)
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