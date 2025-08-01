import json
import random
import time
import requests
import logging
import sys
from io import StringIO
from playwright.sync_api import sync_playwright
from datetime import datetime

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

    def handle_cloudflare(self):
        """Enhanced Cloudflare challenge handler"""
        max_wait = 120  # Maximum wait time in seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # Check for different Cloudflare challenge types
                if self.page.locator("div#challenge-stage").count() > 0:
                    logging.info("⏳ Cloudflare verification detected (Challenge Stage)")
                    self.page.wait_for_selector("div#challenge-stage", state="hidden", timeout=30000)
                    logging.info("✅ Cloudflare verification passed")
                    return True
                
                if self.page.locator('text="Verify you are human"').count() > 0:
                    logging.info("⏳ Cloudflare human verification detected")
                    self.page.screenshot(path="cloudflare_challenge.png")
                    self.send_telegram("⚠️ Manual intervention needed: Cloudflare human verification required", "cloudflare_challenge.png")
                    return False
                
                if self.page.locator('text="Checking your browser"').count() > 0:
                    logging.info("⏳ Cloudflare browser check detected")
                    self.page.wait_for_selector('text="Checking your browser"', state="hidden", timeout=30000)
                    logging.info("✅ Cloudflare browser check passed")
                    return True
                
                # If no challenge detected but page isn't loading
                if time.time() - start_time > 30:
                    if self.page.locator("body").count() == 0:
                        raise Exception("Page failed to load")
                    return True
                    
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Cloudflare handling error: {str(e)}")
                self.page.screenshot(path="cloudflare_error.png")
                raise

        raise Exception("Cloudflare verification timeout")

    def login(self):
        """Login with Cloudflare challenge handling"""
        max_retries = 3
        login_url = "https://www.popmart.com/us/user/login?redirect=%2Faccount"
        
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"🔐 Login attempt {attempt}/{max_retries}")
                
                # Navigate to login page with retry
                self.page.goto(login_url, timeout=60000)
                
                # Handle Cloudflare before proceeding
                if not self.handle_cloudflare():
                    raise Exception("Cloudflare verification failed")
                
                # Fill email
                email_field = self.page.locator('input#email, input[placeholder*="e-mail"]')
                email_field.wait_for(timeout=30000)
                email_field.fill(self.config["email"])
                self.random_delay(1, 2)
                
                # Handle terms checkbox if exists
                terms_checkbox = self.page.locator('input[type="checkbox"]').first
                if terms_checkbox.count() > 0:
                    terms_checkbox.check()
                    self.random_delay(1, 2)
                
                # Click continue
                continue_btn = self.page.locator('button:has-text("CONTINUE")')
                continue_btn.click(timeout=30000)
                
                # Handle potential Cloudflare again
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
        """Launch browser with Cloudflare bypass settings"""
        return self.playwright.chromium.launch(
            headless=False,  # Critical for Cloudflare
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ],
            slow_mo=100,  # Simulate human-like delays
            timeout=60000
        )

    def create_context(self):
        """Create context with realistic settings"""
        return self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            # Enable storage state to persist cookies
            storage_state="auth.json" if os.path.exists("auth.json") else None
        )

    def monitor_products(self):
        """Main monitoring loop with Cloudflare handling"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.launch_browser()
            self.context = self.create_context()
            self.page = self.context.new_page()
            
            # Initial navigation with Cloudflare handling
            self.page.goto("https://www.popmart.com/us", timeout=60000)
            if not self.handle_cloudflare():
                raise Exception("Initial Cloudflare verification failed")
            
            # Login sequence
            if not self.login():
                raise Exception("Cannot proceed without login")
            
            # Save authentication state
            self.context.storage_state(path="auth.json")
            
            # Main monitoring loop
            while True:
                for product in self.config["products"]:
                    try:
                        self.process_product(product)
                    except Exception as e:
                        logging.error(f"Product error: {str(e)}")
                        continue
                
                logging.info(f"♻️ Cycle complete. Next in {self.config['scan_interval']}s")
                time.sleep(self.config["scan_interval"])
                
        except Exception as e:
            logging.critical(f"💀 Fatal error: {str(e)}", exc_info=True)
            raise
        finally:
            # Cleanup
            if hasattr(self, 'page') and self.page:
                self.page.close()
            if hasattr(self, 'context') and self.context:
                self.context.close()
            if hasattr(self, 'browser') and self.browser:
                self.browser.close()
            if hasattr(self, 'playwright') and self.playwright:
                self.playwright.stop()

if __name__ == "__main__":
    bot = PopMartBot("config.json")
    try:
        bot.monitor_products()
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.critical(f"💀 Fatal error: {str(e)}", exc_info=True)