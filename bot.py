import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp
import json
import os
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        if not os.path.exists(self.config_file):
            logger.error(f"Configuration file '{self.config_file}' not found!")
            raise FileNotFoundError(f"Configuration file '{self.config_file}' not found")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_file}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
    def get(self, *keys):
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def validate_config(self):
        required_fields = [
            ('telegram', 'bot_token'),
            ('telegram', 'chat_id'),
            ('product_settings', 'url')
        ]
        
        missing_fields = []
        for field_path in required_fields:
            if not self.get(*field_path):
                missing_fields.append('.'.join(field_path))
        
        if missing_fields:
            logger.error(f"Missing required configuration fields: {', '.join(missing_fields)}")
            raise ValueError(f"Missing required configuration: {missing_fields}")
        
        logger.info("Configuration validation passed")

class StealthPopMartMonitor:
    def __init__(self, config_manager):
        self.config = config_manager
        
        # Telegram settings
        self.telegram_bot_token = self.config.get('telegram', 'bot_token')
        self.telegram_chat_id = self.config.get('telegram', 'chat_id')
        
        # Account settings
        self.email = self.config.get('popmart_account', 'email')
        self.password = self.config.get('popmart_account', 'password')
        
        # Product settings
        self.product_url = self.config.get('product_settings', 'url')
        self.preferred_size = self.config.get('product_settings', 'size') or "Single box"
        self.desired_quantity = self.config.get('product_settings', 'quantity') or 1
        
        # Monitoring settings
        self.check_interval = self.config.get('monitoring', 'check_interval') or 60
        self.max_consecutive_errors = self.config.get('monitoring', 'max_consecutive_errors') or 5
        
        # Always use headless mode for stealth
        self.headless_mode = True

    async def send_telegram_message(self, message):
        """Send a message via Telegram Bot API"""
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Telegram message sent successfully")
                    else:
                        logger.error(f"Failed to send Telegram message: {response.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    async def create_stealth_browser(self, playwright):
        """Create a stealth browser that looks like a real user"""
        
        # Random user agents to rotate
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        # Enhanced stealth arguments
        browser_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--disable-gpu",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-default-apps",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--window-size=1920,1080",
            "--user-agent=" + random.choice(user_agents)
        ]
        
        # Launch browser
        browser = await playwright.chromium.launch(
            headless=self.headless_mode,
            args=browser_args
        )
        
        # Create context with stealth settings
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(user_agents),
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'longitude': -74.006, 'latitude': 40.7128},  # New York
            color_scheme='light',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Cache-Control': 'max-age=0',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        # Create page
        page = await context.new_page()
        
        # Add stealth JavaScript
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Mock chrome object
            window.chrome = {
                runtime: {},
            };
            
            // Remove automation indicators
            delete window.__playwright;
            delete window.__pw_manual;
            
            // Mock touch support
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => 1,
            });
        """)
        
        return browser, page

    async def human_like_navigation(self, page, url):
        """Navigate like a human with random delays"""
        
        # Random delay before navigation
        await asyncio.sleep(random.uniform(1, 3))
        
        # Navigate to homepage first (more human-like)
        logger.info("🏠 Visiting homepage first...")
        try:
            await page.goto("https://www.popmart.com/us", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(2, 4))
        except:
            logger.warning("Could not visit homepage, going directly to product")
        
        # Now navigate to the actual product
        logger.info(f"🎯 Navigating to product: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Random mouse movements and scrolling
        await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        
        # Random scroll
        await page.evaluate(f"window.scrollTo(0, {random.randint(100, 500)})")
        await asyncio.sleep(random.uniform(1, 2))
        
        # Wait for page to be fully loaded
        await page.wait_for_load_state("networkidle", timeout=15000)

    async def handle_popups_and_modals(self, page):
        """Handle all popups and modals"""
        try:
            # Handle location popup
            location_close = await page.query_selector('.index_closeIcon__oBwY4')
            if location_close:
                logger.info("Closing location popup")
                await location_close.click()
                await asyncio.sleep(1)
            
            # Handle privacy policy
            accept_btn = await page.query_selector('.policy_acceptBtn__ZNU71')
            if accept_btn:
                logger.info("Accepting privacy policy")
                await accept_btn.click()
                await asyncio.sleep(1)
            
            # Handle any error modals
            error_modal = await page.query_selector('.ant-modal-content')
            if error_modal:
                ok_btn = await error_modal.query_selector('.layout_wafErrorModalButton__yJdyc')
                if ok_btn:
                    logger.info("Handling error modal")
                    await ok_btn.click()
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.debug(f"Error handling popups: {e}")

    async def check_product_availability(self, page):
        """Check if product is available with multiple methods"""
        try:
            # Wait a bit for dynamic content
            await asyncio.sleep(3)
            
            # Handle popups first
            await self.handle_popups_and_modals(page)
            
            # Get product title
            product_title = "PopMart Product"
            try:
                title_element = await page.query_selector('h1, [class*="title"], .product-name')
                if title_element:
                    product_title = await title_element.inner_text()
            except:
                pass
            
            logger.info(f"📦 Checking product: {product_title}")
            
            # Method 1: Check the exact PopMart button
            add_to_bag_btn = await page.query_selector('.index_usBtn__2KlEx.index_red__kx6Ql.index_btnFull__F7k90')
            if add_to_bag_btn:
                button_text = await add_to_bag_btn.inner_text()
                is_visible = await add_to_bag_btn.is_visible()
                is_enabled = await add_to_bag_btn.is_enabled()
                
                logger.info(f"🔘 Button found: '{button_text}' | Visible: {is_visible} | Enabled: {is_enabled}")
                
                if is_visible and is_enabled and "ADD TO BAG" in button_text.upper():
                    logger.info("🎉 PRODUCT IS AVAILABLE!")
                    
                    # Send notification
                    message = f"""
🎉 <b>PopMart Product Available!</b>

🧸 <b>Product:</b> {product_title}
📏 <b>Size:</b> {self.preferred_size}
📦 <b>Quantity:</b> {self.desired_quantity}
🔗 <b>URL:</b> {self.product_url}
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ The "ADD TO BAG" button is now active!
🏃‍♂️ Hurry up and complete your purchase!
                    """
                    
                    await self.send_telegram_message(message.strip())
                    return True
            
            # Method 2: Check for any button with "add to bag" text
            all_buttons = await page.query_selector_all('button, div[role="button"], .btn')
            for button in all_buttons:
                try:
                    text = await button.inner_text()
                    if "ADD TO BAG" in text.upper() or "ADD TO CART" in text.upper():
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        logger.info(f"🔘 Found button: '{text}' | Visible: {is_visible} | Enabled: {is_enabled}")
                        
                        if is_visible and is_enabled:
                            logger.info("🎉 PRODUCT IS AVAILABLE!")
                            return True
                except:
                    continue
            
            # Method 3: Look for out of stock indicators
            out_of_stock_indicators = [
                'sold out', 'out of stock', 'unavailable', 'coming soon'
            ]
            
            page_text = await page.inner_text('body')
            for indicator in out_of_stock_indicators:
                if indicator.lower() in page_text.lower():
                    logger.info(f"❌ Found out of stock indicator: {indicator}")
                    return False
            
            logger.info("❌ Product not available - no active ADD TO BAG button found")
            return False
            
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return False

    async def monitor_product(self):
        """Main monitoring function with stealth"""
        logger.info(f"🥷 Starting STEALTH PopMart monitor")
        logger.info(f"🎯 Target: {self.product_url}")
        
        # Send start notification
        if self.config.get('notifications', 'send_start_notification', True):
            start_message = f"""
🥷 <b>Stealth PopMart Monitor Started!</b>

🧸 <b>Product:</b> {self.product_url}
📏 <b>Size:</b> {self.preferred_size}  
📦 <b>Quantity:</b> {self.desired_quantity}
⏰ <b>Check Interval:</b> {self.check_interval} seconds
🛡️ <b>Mode:</b> Anti-Detection Stealth

🔍 Monitoring started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            await self.send_telegram_message(start_message.strip())
        
        async with async_playwright() as p:
            browser, page = await self.create_stealth_browser(p)
            
            try:
                consecutive_errors = 0
                
                while True:
                    try:
                        logger.info(f"🔍 Checking product at {datetime.now().strftime('%H:%M:%S')}")
                        
                        # Human-like navigation
                        await self.human_like_navigation(page, self.product_url)
                        
                        # Check availability
                        is_available = await self.check_product_availability(page)
                        
                        if is_available:
                            logger.info("🎉 Product is available! Alert sent.")
                            # Continue monitoring or break here
                            # break
                        else:
                            logger.info("❌ Product not available yet...")
                        
                        consecutive_errors = 0
                        
                        # Random wait time (more human-like)
                        wait_time = self.check_interval + random.randint(-10, 10)
                        logger.info(f"⏳ Waiting {wait_time} seconds before next check...")
                        await asyncio.sleep(wait_time)
                        
                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"Error ({consecutive_errors}/{self.max_consecutive_errors}): {e}")
                        
                        if consecutive_errors >= self.max_consecutive_errors:
                            error_msg = f"❌ Stealth monitor stopped after {self.max_consecutive_errors} errors. Last: {e}"
                            logger.error(error_msg)
                            await self.send_telegram_message(error_msg)
                            break
                        
                        # Longer wait on error
                        await asyncio.sleep(60)
                        
            except KeyboardInterrupt:
                stop_msg = "⏹️ Stealth monitor stopped by user"
                logger.info(stop_msg)
                await self.send_telegram_message(stop_msg)
            finally:
                await browser.close()

async def main():
    try:
        config_manager = ConfigManager("config.json")
        config_manager.validate_config()
        
        monitor = StealthPopMartMonitor(config_manager)
        await monitor.monitor_product()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())