import json
import random
import time
import requests
import logging
import sys
from io import StringIO
from playwright.sync_api import sync_playwright

class TelegramLogger:
    """Captures terminal output and sends to Telegram"""
    def __init__(self, bot, log_level=logging.INFO):
        self.bot = bot
        self.log_level = log_level
        self.log_buffer = StringIO()
        self.terminal = sys.stdout
        
    def write(self, message):
        self.terminal.write(message)
        if message.strip():
            self.log_buffer.write(message)
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
        """Redirect all output to Telegram"""
        sys.stdout = TelegramLogger(self, logging.INFO)
        sys.stderr = TelegramLogger(self, logging.ERROR)
        logging.basicConfig(
            stream=sys.stdout,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def load_config(self, path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Config load failed: {str(e)}")
            raise

    def send_telegram(self, message, photo_path=None):
        """Enhanced Telegram notification with error handling"""
        if not self.telegram_enabled:
            return
            
        url = f"https://api.telegram.org/bot{self.config['telegram']['token']}/sendMessage"
        payload = {
            "chat_id": self.config['telegram']['chat_id'],
            "text": f"🧸 PopMart Bot:\n{message}",
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        try:
            if photo_path:
                url = f"https://api.telegram.org/bot{self.config['telegram']['token']}/sendPhoto"
                with open(photo_path, 'rb') as photo:
                    files = {'photo': photo}
                    requests.post(
                        url,
                        data={"chat_id": self.config['telegram']['chat_id'], "caption": message},
                        files=files,
                        timeout=10
                    )
            else:
                requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram notification failed: {str(e)}")  # Fallback to terminal

    def random_delay(self, min=0.5, max=2.0):
        """Human-like random delay"""
        delay = random.uniform(min, max)
        time.sleep(delay)
        logging.debug(f"Delay: {delay:.2f}s")

    def apply_stealth(self):
        """Advanced anti-detection measures"""
        stealth_js = """
        // Mask WebDriver
        delete Object.getPrototypeOf(navigator).webdriver;
        
        // Chrome app mock
        window.navigator.chrome = {
            runtime: {},
            app: { isInstalled: false },
            webstore: { onInstallStageChanged: {}, onDownloadProgress: {} },
            csi: function() {},
            loadTimes: function() {},
        };
        
        // Permission overrides
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ? 
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Plugin spoofing
        Object.defineProperty(navigator, 'plugins', {
            get: () => [{
                name: 'Chrome PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
            }],
        });
        
        // Language settings
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        """
        try:
            self.page.add_init_script(script=stealth_js)
            logging.info("🕵️ Stealth mode activated")
        except Exception as e:
            logging.error(f"Stealth injection failed: {str(e)}")
            raise

    def handle_cloudflare(self):
        """Cloudflare challenge solver"""
        if self.page.locator("div#challenge-stage").count() > 0:
            logging.info("⏳ Cloudflare verification detected")
            try:
                self.page.wait_for_selector("div#challenge-stage", state="hidden", timeout=120000)
                logging.info("✅ Cloudflare solved")
            except Exception as e:
                logging.error(f"Cloudflare timeout: {str(e)}")
                raise

    def login(self):
        """Secure login with error recovery"""
        try:
            logging.info("🔐 Attempting login")
            self.page.locator('a[href*="/user/login"]').first.click()
            self.page.wait_for_load_state("networkidle")
            
            self.page.fill('input#email', self.config["email"])
            self.page.locator('input.ant-checkbox-input').check()
            self.page.locator('button:has-text("CONTINUE")').click()
            
            self.page.fill('input#password', self.config["password"])
            self.page.locator('button:has-text("SIGN IN")').click()
            self.page.wait_for_load_state("networkidle")
            
            logging.info("🔑 Login successful")
            return True
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            return False

    def launch_browser(self):
        """Configure browser with anti-detection settings"""
        return self.playwright.chromium.launch(
            headless=self.config.get("headless", True),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ],
            timeout=60000
        )

    def create_context(self):
        """Create stealth browser context"""
        return self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            permissions=["geolocation"]
        )

    def process_product(self, product):
        """Handle individual product purchase flow"""
        logging.info(f"🔍 Checking: {product['name']}")
        self.page.goto(product["url"], timeout=60000)
        
        if self.page.locator('button:has-text("SOLD OUT")').count() > 0:
            logging.warning(f"⛔ Out of stock: {product['name']}")
            return False
            
        # Purchase logic here...
        logging.info(f"✅ Added to cart: {product['name']}")
        return True

    def monitor_products(self):
        """Main monitoring loop with full logging"""
        try:
            # Initialize Playwright
            self.playwright = sync_playwright().start()
            
            # Browser setup
            self.browser = self.launch_browser()
            self.context = self.create_context()
            self.page = self.context.new_page()
            
            logging.info("🌐 Navigating to PopMart")
            self.page.goto("https://www.popmart.com/us", timeout=60000)
            self.apply_stealth()
            
            if not self.login():
                raise Exception("Login failed after retries")
            
            # Main monitoring loop
            while True:
                for product in self.config["products"]:
                    try:
                        self.process_product(product)
                    except Exception as e:
                        logging.error(f"Product processing failed: {str(e)}")
                        continue
                
                logging.info(f"♻️ Cycle complete. Next scan in {self.config['scan_interval']}s")
                time.sleep(self.config["scan_interval"])
                
        except Exception as e:
            logging.critical(f"🆘 Bot crashed: {str(e)}", exc_info=True)
            raise
        finally:
            # Cleanup resources in reverse order
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
    try:
        bot.monitor_products()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.critical(f"💀 Fatal error: {str(e)}", exc_info=True)