import asyncio
import json
import random
import time
import requests
from playwright.async_api import async_playwright

# Telegram Configuration - Update with your details
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# Bot Configuration - Update these values
CONFIG = {
    "email": "your_email@example.com",
    "password": "your_password",
    "products": [
        {
            "url": "https://www.popmart.com/us/product/labubu-123",
            "size": "Single box",
            "quantity": 1
        },
        {
            "url": "https://www.popmart.com/us/product/popmart-456",
            "size": "Whole set",
            "quantity": 3
        }
    ],
    "retry_limit": 10,
    "monitor_interval": 30  # seconds between stock checks
}

class TelegramNotifier:
    @staticmethod
    async def send(message):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"Telegram API error: {response.text}")
        except Exception as e:
            print(f"Failed to send Telegram notification: {str(e)}")
        
        # Also print to console
        print(message)

class PopMartBot:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.retry_count = 0
        self.notifier = TelegramNotifier()

    async def launch_browser(self):
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized"
                ]
            )
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.114 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                java_script_enabled=True
            )
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.originalOpen = window.open;
                window.open = function(url) { return window.originalOpen(url, '_self'); };
            """)
            self.page = await self.context.new_page()
            await self.notifier.send("🚀 <b>PopMart Bot Started</b>\nBrowser launched successfully")
            return True
        except Exception as e:
            error_msg = f"❌ <b>Browser Launch Failed</b>\n{str(e)}"
            await self.notifier.send(error_msg)
            return False

    async def handle_location(self):
        try:
            # Wait for location selection to appear
            await self.page.wait_for_selector('div.index_ipInCountry__BoVSZ:has-text("United States")', timeout=15000)
            await self.page.click('div.index_ipInCountry__BoVSZ:has-text("United States")')
            
            # Accept privacy policy
            await self.page.wait_for_selector('div.policy_acceptBtn__ZNU71:has-text("ACCEPT")', timeout=10000)
            await self.page.click('div.policy_acceptBtn__ZNU71:has-text("ACCEPT")')
            
            await self.notifier.send("📍 Location set to <b>United States</b>")
            return True
        except Exception as e:
            error_msg = f"❌ <b>Location Handling Failed</b>\n{str(e)}"
            await self.notifier.send(error_msg)
            return False

    async def login(self):
        try:
            # Click user icon
            await self.page.click('a[href*="/user/login"]')
            
            # Enter email
            await self.page.wait_for_selector('input#email', timeout=10000)
            await self.page.fill('input#email', CONFIG["email"])
            await self.page.click('button:has-text("CONTINUE")')
            
            # Enter password
            await self.page.wait_for_selector('input#password', timeout=5000)
            await self.page.fill('input#password', CONFIG["password"])
            await self.page.click('button:has-text("SIGN IN")')
            
            # Verify login success
            await self.page.wait_for_selector('div.header_infoTitle__Fse4B', timeout=15000)
            
            await self.notifier.send(f"🔑 <b>Login Successful</b>\nAccount: {CONFIG['email']}")
            return True
        except Exception as e:
            error_msg = f"❌ <b>Login Failed</b>\n{str(e)}"
            await self.notifier.send(error_msg)
            return False

    async def add_product_to_cart(self, product):
        try:
            await self.page.goto(product["url"])
            print(f"Processing product: {product['url']}")
            
            # Select size
            size_selector = f'div.index_sizeInfoTitle__kpZbS:has-text("{product["size"]}")'
            await self.page.wait_for_selector(size_selector, timeout=10000)
            await self.page.click(size_selector)
            
            # Set quantity
            current_qty = 1
            while current_qty < product["quantity"]:
                await self.page.click('div.index_quantityInfoBlock__ZixOe >> div.index_countButton__mJU5Q:not(.index_disableBtn__cDpGw) >> nth=1')
                current_qty += 1
                await asyncio.sleep(random.uniform(0.3, 0.8))  # Human-like delay
            
            # Add to bag
            await self.page.click('div.index_usBtn__2KIEx:has-text("ADD TO BAG")')
            
            # Handle post-add dialog
            await self.page.wait_for_selector('div.ant-notification-notice-message:has-text("Added To Bag")', timeout=5000)
            
            # For last product, go to cart; otherwise continue shopping
            if product == CONFIG["products"][-1]:
                await self.page.click('button:has-text("View Bag")')
            else:
                await self.page.click('button:has-text("Continue Shopping")')
            
            product_name = product["url"].split("/")[-1]
            success_msg = f"🛒 <b>Added to Cart</b>\nProduct: {product_name}\nSize: {product['size']}\nQuantity: {product['quantity']}"
            await self.notifier.send(success_msg)
            return True
        except Exception as e:
            error_msg = f"❌ <b>Add to Cart Failed</b>\nProduct: {product['url']}\nError: {str(e)}"
            await self.notifier.send(error_msg)
            return False

    async def checkout(self):
        try:
            # Select all items
            await self.page.wait_for_selector('div.index_selectText__HDXz:has-text("Select all")', timeout=10000)
            await self.page.click('div.index_selectText__HDXz:has-text("Select all")')
            
            # Proceed to checkout
            await self.page.click('button:has-text("CHECK OUT")')
            await self.notifier.send("🛒 <b>Proceeding to Checkout</b>")
            
            # Handle Cloudflare verification if present
            try:
                await self.page.wait_for_selector('div#challenge-container', timeout=3000)
                await self.notifier.send("🛡️ <b>Cloudflare Verification</b>\nWaiting for completion...")
                await self.page.wait_for_selector('div#challenge-container', state="hidden", timeout=120000)
                await self.notifier.send("✅ <b>Cloudflare Verification Complete</b>")
            except:
                pass
            
            # Proceed to payment
            await self.page.wait_for_selector('button:has-text("Proceed to Pay")', timeout=15000)
            await self.page.click('button:has-text("Proceed to Pay")')
            await self.notifier.send("💳 <b>Processing Payment</b>")
            
            # Handle high volume warning
            try:
                await self.page.wait_for_selector('div.ant-modal-title:has-text("Oops")', timeout=3000)
                await self.notifier.send("⚠️ <b>High Volume Warning</b>\nRetrying checkout...")
                await self.page.click('button:has-text("OK")')
                return False  # Indicate need for retry
            except:
                pass
            
            # Select credit card and complete payment
            await self.page.wait_for_selector('div:has-text("CreditCard")', timeout=10000)
            await self.page.click('div.index_radiowWrap__RIGKZ:has-text("CreditCard")')
            await self.page.click('button.adyen-checkout__button--pay')
            
            # Verify purchase completion
            await self.page.wait_for_selector('div:has-text("Order Confirmation")', timeout=30000)
            
            # Get order total
            try:
                order_total = await self.page.text_content('div.index_totalAmount__9XZqU')
                success_msg = f"🎉 <b>PURCHASE SUCCESSFUL!</b>\nOrder Total: {order_total}"
                await self.notifier.send(success_msg)
            except:
                await self.notifier.send("🎉 <b>PURCHASE SUCCESSFUL!</b>")
            
            return True
        except Exception as e:
            error_msg = f"❌ <b>Checkout Failed</b>\nError: {str(e)}"
            await self.notifier.send(error_msg)
            return False

    async def monitor_and_purchase(self):
        await self.notifier.send("🚀 <b>Starting PopMart Bot</b>")
        
        if not await self.launch_browser():
            return
            
        while True:
            try:
                # Initial navigation
                await self.page.goto("https://www.popmart.com/us", timeout=60000)
                await self.notifier.send("🌐 Navigating to PopMart US")
                
                # Handle location and login
                if not await self.handle_location():
                    continue
                
                if not await self.login():
                    await self.page.goto("https://www.popmart.com/us")
                    continue
                
                # Process all products
                success = True
                for product in CONFIG["products"]:
                    if not await self.add_product_to_cart(product):
                        success = False
                        break
                    await asyncio.sleep(random.uniform(1, 3))
                
                if not success:
                    await self.notifier.send("🔄 Restarting process after cart error")
                    await self.page.goto("https://www.popmart.com/us")
                    continue
                
                # Complete checkout with retries
                checkout_success = False
                for attempt in range(CONFIG["retry_limit"]):
                    if await self.checkout():
                        checkout_success = True
                        break
                    retry_msg = f"🔄 <b>Checkout Retry</b>\nAttempt {attempt+1}/{CONFIG['retry_limit']}"
                    await self.notifier.send(retry_msg)
                    await asyncio.sleep(CONFIG["monitor_interval"])
                
                if checkout_success:
                    # Reset for next monitoring cycle
                    await self.notifier.send("🔍 <b>Monitoring for next restock</b>")
                    await self.page.goto("https://www.popmart.com/us")
                    self.retry_count = 0
                else:
                    await self.notifier.send("❌ <b>Checkout Failed After Retries</b>")
                
                # Wait before next check
                await asyncio.sleep(CONFIG["monitor_interval"])
                
            except Exception as e:
                error_msg = f"❌ <b>Critical Error</b>\n{str(e)}"
                await self.notifier.send(error_msg)
                self.retry_count += 1
                if self.retry_count > 5:
                    await self.notifier.send("🔄 <b>Too many errors - Restarting Browser</b>")
                    await self.browser.close()
                    if not await self.launch_browser():
                        return
                    self.retry_count = 0
                else:
                    await self.page.goto("https://www.popmart.com/us")
                await asyncio.sleep(10)

    async def run(self):
        while True:
            try:
                await self.monitor_and_purchase()
            except Exception as e:
                error_msg = f"💥 <b>Fatal Error</b>\n{str(e)}\nRestarting in 30 seconds..."
                await self.notifier.send(error_msg)
                if self.browser:
                    await self.browser.close()
                await asyncio.sleep(30)
                await self.launch_browser()

if __name__ == "__main__":
    bot = PopMartBot()
    asyncio.run(bot.run())
