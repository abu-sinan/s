import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp
import json
import os
from pathlib import Path

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
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            logger.error(f"Configuration file '{self.config_file}' not found!")
            logger.info("Please create a config.json file with your settings.")
            raise FileNotFoundError(f"Configuration file '{self.config_file}' not found")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_file}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def get(self, *keys):
        """Get nested configuration value"""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def validate_config(self):
        """Validate required configuration fields"""
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

class PopMartMonitor:
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
        self.headless_mode = self.config.get('monitoring', 'headless_mode') or False
        
        # Browser settings
        self.user_agent = self.config.get('browser_settings', 'user_agent') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.viewport_width = self.config.get('browser_settings', 'viewport_width') or 1920
        self.viewport_height = self.config.get('browser_settings', 'viewport_height') or 1080
        self.timeout = self.config.get('browser_settings', 'timeout') or 30000
        
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

    async def wait_for_cloudflare(self, page, timeout=30000):
        """Wait for Cloudflare protection to complete"""
        logger.info("Checking for Cloudflare protection...")
        
        try:
            # Wait for page to load
            await page.wait_for_load_state("networkidle", timeout=timeout)
            
            # Check for Cloudflare challenge indicators
            cloudflare_selectors = [
                '[data-ray]',
                '.cf-browser-verification',
                '#cf-challenge-running',
                '.cf-checking-browser',
                'div[class*="cf-"]',
                '.challenge-running'
            ]
            
            for selector in cloudflare_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        logger.info("Cloudflare protection detected, waiting for completion...")
                        await page.wait_for_selector(selector, state="detached", timeout=timeout)
                        logger.info("Cloudflare protection completed")
                        break
                except:
                    continue
                    
            # Additional wait for stability
            await page.wait_for_load_state("networkidle")
            logger.info("Page loaded successfully")
            
        except Exception as e:
            logger.warning(f"Cloudflare wait timeout or error: {e}")

    async def handle_location_popup(self, page):
        """Handle the US location popup"""
        try:
            # Check for location popup
            location_popup = await page.query_selector('.index_ipWarnContainer__d5qTd')
            if location_popup:
                logger.info("Location popup detected")
                # Click close button
                close_btn = await page.query_selector('.index_closeIcon__oBwY4')
                if close_btn:
                    await close_btn.click()
                    logger.info("Location popup closed")
                    await page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug(f"Location popup handling error: {e}")

    async def handle_privacy_policy(self, page):
        """Handle privacy policy acceptance"""
        try:
            # Check for privacy policy popup
            policy_popup = await page.query_selector('.policy_aboveFixedContainer__KfeZi')
            if policy_popup:
                logger.info("Privacy policy popup detected")
                # Click accept button
                accept_btn = await page.query_selector('.policy_acceptBtn__ZNU71')
                if accept_btn:
                    await accept_btn.click()
                    logger.info("Privacy policy accepted")
                    await page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug(f"Privacy policy handling error: {e}")

    async def handle_login(self, page):
        """Handle login process if credentials are provided"""
        if not self.email or not self.password:
            logger.info("No login credentials provided, skipping login")
            return False
            
        try:
            # Check if email input is present (login required)
            email_input = await page.query_selector('#email')
            if email_input:
                logger.info("Login required, attempting to log in...")
                
                # Enter email
                await email_input.fill(self.email)
                await page.wait_for_timeout(500)
                
                # Check and click terms checkbox if present
                terms_checkbox = await page.query_selector('.index_serviceCheckbox__KjCpl input[type="checkbox"]')
                if terms_checkbox:
                    await terms_checkbox.click()
                    await page.wait_for_timeout(500)
                
                # Click continue button
                continue_btn = await page.query_selector('.index_loginButton__O6r8l')
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(2000)
                
                # Enter password
                password_input = await page.query_selector('#password')
                if password_input:
                    await password_input.fill(self.password)
                    await page.wait_for_timeout(500)
                    
                    # Click sign in
                    signin_btn = await page.query_selector('button[type="submit"].index_loginButton__O6r8l')
                    if signin_btn:
                        await signin_btn.click()
                        await page.wait_for_timeout(3000)
                        logger.info("Login completed")
                        return True
                        
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
        
        return False

    async def handle_error_modals(self, page):
        """Handle error modals like 'High order volume'"""
        try:
            # Check for "Oops" modal
            error_modal = await page.query_selector('.ant-modal-content')
            if error_modal:
                title_element = await error_modal.query_selector('.ant-modal-title')
                if title_element:
                    title_text = await title_element.inner_text()
                    if "Oops" in title_text:
                        logger.warning("Error modal detected: High order volume")
                        # Click OK button
                        ok_btn = await error_modal.query_selector('.layout_wafErrorModalButton__yJdyc')
                        if ok_btn:
                            await ok_btn.click()
                            await page.wait_for_timeout(1000)
                            return True
        except Exception as e:
            logger.debug(f"Error modal handling: {e}")
        
        return False

    async def select_size_and_quantity(self, page):
        """Select the preferred size and quantity"""
        try:
            # Handle size selection
            size_container = await page.query_selector('.index_sizeContainer__qtqKx')
            if size_container:
                logger.info(f"Size container found, looking for: {self.preferred_size}")
                
                # Get all size options
                size_options = await size_container.query_selector_all('.index_sizeInfoItem__f_Uxb')
                
                for option in size_options:
                    size_text_element = await option.query_selector('.index_sizeInfoTitle__kpZbS')
                    if size_text_element:
                        size_text = await size_text_element.inner_text()
                        if self.preferred_size.lower() in size_text.lower():
                            # Check if this size is already active
                            is_active = await option.query_selector('.index_active__CP2n5')
                            if not is_active:
                                logger.info(f"Selecting size: {size_text}")
                                await option.click()
                                await page.wait_for_timeout(1000)
                            else:
                                logger.info(f"Size '{size_text}' already selected")
                            break
                else:
                    logger.warning(f"Preferred size '{self.preferred_size}' not found, using default")
            
            # Handle quantity selection
            if self.desired_quantity > 1:
                quantity_container = await page.query_selector('.index_quantityContainer__OhYal')
                if quantity_container:
                    current_quantity = 1
                    plus_button = await quantity_container.query_selector('.index_countButton__mJU5Q:not(.index_disableBtn__cDpGw)')
                    
                    while current_quantity < self.desired_quantity and plus_button:
                        await plus_button.click()
                        await page.wait_for_timeout(500)
                        current_quantity += 1
                        
                        # Check if plus button is still enabled
                        plus_button = await quantity_container.query_selector('.index_countButton__mJU5Q:not(.index_disableBtn__cDpGw)')
                    
                    logger.info(f"Quantity set to: {current_quantity}")
                    
        except Exception as e:
            logger.error(f"Error selecting size/quantity: {e}")

    async def check_product_availability(self, page):
        """Check if product can be added to bag"""
        try:
            # Get product title
            product_title = "PopMart Product"
            try:
                title_element = await page.query_selector('h1, .product-title, [class*="title"]')
                if title_element:
                    product_title = await title_element.inner_text()
            except:
                pass
            
            # Select preferred size and quantity
            await self.select_size_and_quantity(page)
            
            # Check quantity controls
            quantity_container = await page.query_selector('.index_quantityContainer__OhYal')
            if quantity_container:
                # Check if quantity input is enabled
                quantity_input = await quantity_container.query_selector('.index_countInput__2ma_C')
                if quantity_input:
                    is_disabled = await quantity_input.get_attribute('disabled')
                    if is_disabled:
                        logger.info("Quantity input is disabled - product not available")
                        return False
            
            # Check the main "ADD TO BAG" button
            add_to_bag_btn = await page.query_selector('.index_usBtn__2KlEx.index_red__kx6Ql.index_btnFull__F7k90')
            if add_to_bag_btn:
                # Check if button is clickable
                is_disabled = await add_to_bag_btn.get_attribute('disabled')
                is_hidden = await add_to_bag_btn.is_hidden()
                
                if not is_disabled and not is_hidden:
                    button_text = await add_to_bag_btn.inner_text()
                    logger.info(f"Add to bag button found: '{button_text}'")
                    
                    if "ADD TO BAG" in button_text.upper():
                        logger.info("🎉 PRODUCT IS AVAILABLE!")
                        
                        # Send success notification
                        if self.config.get('notifications', 'send_availability_alerts'):
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
                    else:
                        logger.info(f"Button text indicates unavailable: {button_text}")
                        return False
                else:
                    logger.info("Add to bag button is disabled or hidden")
                    return False
            else:
                logger.info("Add to bag button not found")
                return False
                
        except Exception as e:
            logger.error(f"Error checking product availability: {e}")
            return False

    async def monitor_product(self):
        """Main monitoring function"""
        logger.info(f"Starting PopMart monitor for: {self.product_url}")
        
        # Send start notification if enabled
        if self.config.get('notifications', 'send_start_notification'):
            start_message = f"""
🚀 <b>PopMart Monitor Started!</b>

🧸 <b>Product:</b> {self.product_url}
📏 <b>Preferred Size:</b> {self.preferred_size}
📦 <b>Quantity:</b> {self.desired_quantity}
⏰ <b>Check Interval:</b> {self.check_interval} seconds
👤 <b>Account:</b> {self.email if self.email else 'Guest'}

🔍 Monitoring started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            await self.send_telegram_message(start_message.strip())
        
        async with async_playwright() as p:
            # Launch browser with settings from config
            browser = await p.chromium.launch(
                headless=self.headless_mode,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--disable-extensions',
                    '--disable-dev-shm-usage',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            
            # Create new page with settings from config
            page = await browser.new_page()
            
            await page.set_extra_http_headers({
                'User-Agent': self.user_agent
            })
            await page.set_viewport_size({
                "width": self.viewport_width, 
                "height": self.viewport_height
            })
            
            try:
                consecutive_errors = 0
                
                while True:
                    try:
                        logger.info(f"🔍 Checking product at {datetime.now().strftime('%H:%M:%S')}")
                        
                        # Navigate to product page
                        await page.goto(self.product_url, wait_until="domcontentloaded", timeout=self.timeout)
                        
                        # Wait for Cloudflare protection
                        await self.wait_for_cloudflare(page)
                        
                        # Handle popups and modals
                        await self.handle_location_popup(page)
                        await self.handle_privacy_policy(page)
                        
                        # Handle error modals
                        error_handled = await self.handle_error_modals(page)
                        if error_handled:
                            logger.info("Error modal handled, retrying in 30 seconds...")
                            await asyncio.sleep(30)
                            continue
                        
                        # Handle login if needed
                        await self.handle_login(page)
                        
                        # Check product availability
                        is_available = await self.check_product_availability(page)
                        
                        if is_available:
                            logger.info("🎉 Product is available! Alert sent.")
                            # You can choose to break here or continue monitoring
                            # break
                        else:
                            logger.info("❌ Product not available yet...")
                        
                        consecutive_errors = 0  # Reset error counter on success
                        
                        # Wait before next check
                        logger.info(f"⏳ Waiting {self.check_interval} seconds before next check...")
                        await asyncio.sleep(self.check_interval)
                        
                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(f"Error during monitoring cycle ({consecutive_errors}/{self.max_consecutive_errors}): {e}")
                        
                        if consecutive_errors >= self.max_consecutive_errors:
                            error_msg = f"❌ Monitor stopped after {self.max_consecutive_errors} consecutive errors. Last error: {e}"
                            logger.error(error_msg)
                            
                            if self.config.get('notifications', 'send_error_notifications'):
                                await self.send_telegram_message(error_msg)
                            break
                        
                        await asyncio.sleep(30)  # Wait 30 seconds on error
                        
            except KeyboardInterrupt:
                stop_msg = "⏹️ PopMart monitor stopped by user"
                logger.info(stop_msg)
                await self.send_telegram_message(stop_msg)
            finally:
                await browser.close()

async def main():
    """Main function to run the monitor"""
    try:
        # Load configuration
        config_manager = ConfigManager("config.json")
        config_manager.validate_config()
        
        # Create and run monitor
        monitor = PopMartMonitor(config_manager)
        await monitor.monitor_product()
        
    except FileNotFoundError:
        print("\n❌ Configuration file not found!")
        print("Please create a 'config.json' file with your settings.")
        print("Check the example configuration for the required format.")
    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
        print("Please check your config.json file.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())