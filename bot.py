import json
import random
import time
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

class PopMartBot:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.browser = None
        self.context = None
        self.page = None
        self.telegram_enabled = 'telegram' in self.config

    def load_config(self, path):
        with open(path) as f:
            return json.load(f)

    def send_telegram(self, message):
        """Send notification via Telegram"""
        if not self.telegram_enabled:
            return
            
        url = f"https://api.telegram.org/bot{self.config['telegram']['token']}/sendMessage"
        payload = {
            "chat_id": self.config['telegram']['chat_id'],
            "text": f"🧸 PopMart Bot:\n{message}",
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram notification failed: {str(e)}")

    def random_delay(self, min=0.5, max=2.0):
        time.sleep(random.uniform(min, max))

    def handle_cloudflare(self):
        """Wait for Cloudflare verification if present"""
        if self.page.locator("div#challenge-stage").count() > 0:
            self.send_telegram("⏳ Cloudflare verification detected, waiting...")
            try:
                self.page.wait_for_selector("div#challenge-stage", state="hidden", timeout=120000)
                self.random_delay(2, 4)
                self.send_telegram("✅ Cloudflare verification completed")
            except Exception as e:
                self.send_telegram(f"❌ Cloudflare timeout: {str(e)}")
                raise

    def handle_location_modal(self):
        """Select United States location"""
        if self.page.locator('div.index_ipInCountry__BoVSZ:has-text("United States")').count() > 0:
            self.page.locator('div.index_ipInCountry__BoVSZ:has-text("United States")').click()
            self.random_delay()
            self.page.locator('div.policy_acceptBtn__ZNU71:has-text("ACCEPT")').click()
            self.random_delay()
            self.send_telegram("📍 Location set to United States")

    def login(self):
        """Perform login sequence"""
        # Click user icon
        self.page.locator('a[href*="/user/login"]').first.click()
        self.page.wait_for_load_state("networkidle")
        self.random_delay()
        
        # Enter email
        self.page.fill('input#email', self.config["email"])
        self.random_delay(0.2, 0.5)
        
        # Check terms box
        self.page.locator('input.ant-checkbox-input').check()
        self.random_delay()
        
        # Click continue
        self.page.locator('button:has-text("CONTINUE")').click()
        self.page.wait_for_load_state("networkidle")
        self.random_delay()
        
        # Enter password and sign in
        self.page.fill('input#password', self.config["password"])
        self.random_delay(0.2, 0.5)
        self.page.locator('button:has-text("SIGN IN")').click()
        self.page.wait_for_load_state("networkidle")
        self.random_delay(2, 3)
        self.send_telegram("🔑 Successfully logged in")

    def add_product_to_cart(self, product):
        """Add product to cart with specified options"""
        self.page.goto(product["url"])
        self.page.wait_for_load_state("networkidle")
        self.random_delay(1, 2)
        self.send_telegram(f"🔍 Checking: {product['name']}")
        
        # Handle Cloudflare if appears
        self.handle_cloudflare()
        
        # Check stock availability
        if self.page.locator('button:has-text("SOLD OUT")').count() > 0:
            self.send_telegram(f"⛔ Out of stock: {product['name']}")
            return False
            
        # Select size
        size_locator = f'div.index_sizeInfoTitle__kpZbS:has-text("{product["size"]}")'
        if self.page.locator(size_locator).count() == 0:
            self.send_telegram(f"❌ Size not found: {product['size']} for {product['name']}")
            return False
            
        self.page.locator(size_locator).click()
        self.random_delay()
        
        # Set quantity
        current_qty = 1
        plus_btn = self.page.locator('div.index_countButton__mJU5Q').last
        while current_qty < product["quantity"]:
            plus_btn.click()
            current_qty += 1
            self.random_delay(0.1, 0.3)
        
        # Add to bag
        self.page.locator('div.index_usBtn__2KIEx:has-text("ADD TO BAG")').click()
        self.random_delay()
        self.send_telegram(f"🛒 Added to cart: {product['name']} x{product['quantity']}")
        
        # View bag
        self.page.locator('button:has-text("View Bag")').click()
        self.page.wait_for_load_state("networkidle")
        self.random_delay(1, 2)
        return True

    def checkout(self):
        """Complete checkout process"""
        # Select all items
        self.page.locator('div.index_checkbox__w_166').click()
        self.random_delay()
        
        # Proceed to checkout
        self.page.locator('button:has-text("CHECK OUT")').click()
        self.page.wait_for_load_state("networkidle")
        self.random_delay(2, 3)
        self.send_telegram("💳 Proceeding to checkout")
        
        # Handle address selection (assuming pre-saved)
        try:
            self.page.locator('button:has-text("PROCEED TO PAY")').click(timeout=10000)
        except:
            pass  # Proceed button might not need interaction
        
        # Handle Cloudflare after checkout
        self.handle_cloudflare()
        
        # Handle high volume error
        if self.page.locator('div.ant-modal-title:has-text("Oops")').count() > 0:
            self.send_telegram("⚠️ High order volume error, retrying...")
            self.page.locator('button:has-text("OK")').click()
            self.random_delay()
            return False  # Indicate need to retry
        
        # Select credit card
        if self.page.locator('div:has-text("CreditCard")').count() == 0:
            self.send_telegram("❌ Credit card option not found")
            return False
            
        self.page.locator('div:has-text("CreditCard")').click()
        self.random_delay()
        
        # Complete payment
        self.page.locator('button.adyen-checkout__button').click()
        self.random_delay(3, 5)
        
        # Verify purchase completion
        if "thank you" in self.page.content().lower():
            self.send_telegram("🎉 Purchase completed successfully!")
            return True
        return False

    def monitor_products(self):
        """Main monitoring and purchase loop"""
        headless = self.config.get("headless", True)
        
        with sync_playwright() as p:
            try:
                self.browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                self.context = self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
                    viewport={"width": 1280, "height": 720}
                )
                self.page = self.context.new_page()
                stealth_sync(self.page)  # Apply anti-detection measures
                
                # Initial navigation
                self.page.goto("https://www.popmart.com/us")
                self.page.wait_for_load_state("networkidle")
                self.random_delay(2, 4)
                self.send_telegram("🤖 Bot started successfully")
                
                # Handle initial modals
                self.handle_cloudflare()
                self.handle_location_modal()
                
                # Perform login
                self.login()
                
                # Main monitoring loop
                while True:
                    for product in self.config["products"]:
                        self.send_telegram(f"🔄 Scanning: {product['name']}")
                        try:
                            if self.add_product_to_cart(product):
                                # Attempt checkout with retries
                                for attempt in range(3):
                                    if self.checkout():
                                        self.send_telegram(f"✅ Successfully purchased {product['name']}!")
                                        break
                                    else:
                                        self.send_telegram(f"⏳ Checkout failed, attempt {attempt+1}/3")
                                        self.random_delay(5, 10)
                        except Exception as e:
                            error_msg = f"❌ Error processing {product['name']}: {str(e)}"
                            self.send_telegram(error_msg)
                        
                        self.random_delay(5, 10)  # Delay between products
                    
                    status = f"♻️ Completed scan cycle. Next in {self.config['scan_interval']}s"
                    self.send_telegram(status)
                    self.random_delay(self.config["scan_interval"], self.config["scan_interval"] + 30)
                    
            except Exception as e:
                self.send_telegram(f"🆘 CRITICAL ERROR: {str(e)}")
                raise
            finally:
                if self.browser:
                    self.browser.close()
                self.send_telegram("🔴 Bot stopped")

if __name__ == "__main__":
    bot = PopMartBot("config.json")
    bot.monitor_products()