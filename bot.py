import asyncio
import logging
from datetime import datetime
import aiohttp
import json
import os
from bs4 import BeautifulSoup
import re

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

class PopMartDebugMonitor:
    def __init__(self, config_manager):
        self.config = config_manager
        self.telegram_bot_token = self.config.get('telegram', 'bot_token')
        self.telegram_chat_id = self.config.get('telegram', 'chat_id')
        self.product_url = self.config.get('product_settings', 'url')
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
        self.session = None

    async def send_telegram_message(self, message):
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
                        return True
                    else:
                        logger.error(f"Failed to send Telegram message: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def create_session(self):
        connector = aiohttp.TCPConnector(
            limit=10,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_page(self, url):
        try:
            async with self.session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    content = await response.text()
                    return content, response.status
                else:
                    logger.warning(f"HTTP {response.status} when fetching {url}")
                    return None, response.status
        except Exception as e:
            logger.error(f"Error fetching page: {e}")
            return None, 0

    def debug_page_content(self, html_content):
        """Debug function to show what's actually on the page"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            print("\n" + "="*80)
            print("🔍 DEBUG: PAGE CONTENT ANALYSIS")
            print("="*80)
            
            # 1. Check page title
            title = soup.find('title')
            print(f"📄 Page Title: {title.get_text(strip=True) if title else 'Not found'}")
            
            # 2. Look for all buttons
            print(f"\n🔘 ALL BUTTONS FOUND:")
            buttons = soup.find_all('button')
            for i, button in enumerate(buttons):
                button_text = button.get_text(strip=True)
                button_classes = button.get('class', [])
                button_disabled = button.get('disabled')
                print(f"  {i+1}. Text: '{button_text}' | Classes: {button_classes} | Disabled: {button_disabled}")
            
            # 3. Look for divs that might be buttons
            print(f"\n📦 DIV ELEMENTS WITH BUTTON-LIKE CLASSES:")
            button_divs = soup.find_all('div', class_=re.compile(r'(btn|button|add.*bag|add.*cart)', re.I))
            for i, div in enumerate(button_divs):
                div_text = div.get_text(strip=True)
                div_classes = div.get('class', [])
                print(f"  {i+1}. Text: '{div_text}' | Classes: {div_classes}")
            
            # 4. Search for specific PopMart classes
            print(f"\n🎯 POPMART-SPECIFIC ELEMENTS:")
            popmart_selectors = [
                '.index_usBtn__2KlEx',
                '.index_red__kx6Ql',
                '.index_btnFull__F7k90',
                '.index_quantityContainer__OhYal',
                '.index_countInput__2ma_C',
                '.index_sizeContainer__qtqKx'
            ]
            
            for selector in popmart_selectors:
                elements = soup.select(selector)
                if elements:
                    for elem in elements:
                        elem_text = elem.get_text(strip=True)
                        elem_classes = elem.get('class', [])
                        elem_disabled = elem.get('disabled')
                        print(f"  ✅ {selector}: '{elem_text}' | Classes: {elem_classes} | Disabled: {elem_disabled}")
                else:
                    print(f"  ❌ {selector}: Not found")
            
            # 5. Search for text containing "add to bag" or similar
            print(f"\n🛒 ELEMENTS WITH 'ADD TO BAG' TEXT:")
            add_to_bag_elements = soup.find_all(text=re.compile(r'add.{0,10}bag|add.{0,10}cart', re.I))
            for text in add_to_bag_elements:
                parent = text.parent
                parent_name = parent.name if parent else 'unknown'
                parent_classes = parent.get('class', []) if parent and hasattr(parent, 'get') else []
                print(f"  📝 Text: '{text.strip()}' | Parent: {parent_name} | Classes: {parent_classes}")
            
            # 6. Look for any availability indicators
            print(f"\n📊 AVAILABILITY INDICATORS:")
            availability_keywords = ['available', 'in stock', 'out of stock', 'sold out', 'unavailable']
            for keyword in availability_keywords:
                elements = soup.find_all(text=re.compile(keyword, re.I))
                if elements:
                    for text in elements:
                        parent = text.parent
                        parent_name = parent.name if parent else 'unknown'
                        print(f"  🏷️  '{keyword}' found: '{text.strip()}' in {parent_name}")
            
            # 7. Check for JavaScript or dynamic content indicators
            print(f"\n⚡ DYNAMIC CONTENT INDICATORS:")
            scripts = soup.find_all('script')
            print(f"  📜 Found {len(scripts)} script tags")
            
            # Look for React or Vue indicators
            react_indicators = soup.find_all(attrs={'data-reactroot': True}) or soup.find_all(id=re.compile(r'react|vue', re.I))
            if react_indicators:
                print(f"  ⚛️  React/Vue detected - content might be dynamically loaded")
            
            # 8. Save full HTML for manual inspection
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"\n💾 Full HTML saved to 'debug_page.html' for manual inspection")
            
            print("="*80)
            print("🔍 DEBUG ANALYSIS COMPLETE")
            print("="*80 + "\n")
            
        except Exception as e:
            logger.error(f"Error in debug analysis: {e}")

    def parse_product_info(self, html_content):
        """Enhanced parsing with debug info"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract product title
            product_title = "PopMart Product"
            title_selectors = ['h1', '.product-title', '[class*="title"]', 'title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    product_title = title_elem.get_text(strip=True)
                    logger.info(f"Found product title with {selector}: {product_title}")
                    break
            
            # Enhanced button detection
            add_to_bag_available = False
            found_buttons = []
            
            # Method 1: Exact PopMart selectors
            exact_selector = '.index_usBtn__2KlEx.index_red__kx6Ql.index_btnFull__F7k90'
            exact_button = soup.select_one(exact_selector)
            if exact_button:
                button_text = exact_button.get_text(strip=True)
                is_disabled = exact_button.get('disabled') is not None
                found_buttons.append(f"Exact selector: '{button_text}' (disabled: {is_disabled})")
                
                if not is_disabled and 'ADD TO BAG' in button_text.upper():
                    add_to_bag_available = True
            
            # Method 2: Individual PopMart classes
            popmart_classes = ['index_usBtn__2KlEx', 'index_red__kx6Ql', 'index_btnFull__F7k90']
            for class_name in popmart_classes:
                elements = soup.select(f'.{class_name}')
                for elem in elements:
                    elem_text = elem.get_text(strip=True)
                    is_disabled = elem.get('disabled') is not None
                    found_buttons.append(f"Class {class_name}: '{elem_text}' (disabled: {is_disabled})")
                    
                    if not is_disabled and elem_text and 'ADD' in elem_text.upper():
                        add_to_bag_available = True
            
            # Method 3: Text-based search
            add_to_bag_texts = soup.find_all(text=re.compile(r'ADD.{0,10}BAG', re.I))
            for text in add_to_bag_texts:
                parent = text.parent
                if parent:
                    parent_tag = parent.name
                    parent_classes = parent.get('class', [])
                    is_disabled = parent.get('disabled') is not None
                    found_buttons.append(f"Text search: '{text.strip()}' in {parent_tag} (disabled: {is_disabled})")
                    
                    if not is_disabled:
                        add_to_bag_available = True
            
            # Method 4: Generic button search
            all_buttons = soup.find_all(['button', 'div', 'a'], text=re.compile(r'add|bag|cart', re.I))
            for button in all_buttons:
                button_text = button.get_text(strip=True)
                is_disabled = button.get('disabled') is not None
                found_buttons.append(f"Generic search: '{button_text}' (disabled: {is_disabled})")
            
            # Log all found buttons
            logger.info("=== FOUND BUTTONS ===")
            for button_info in found_buttons:
                logger.info(f"  {button_info}")
            logger.info("=====================")
            
            # Check quantity input
            quantity_input = soup.select_one('.index_countInput__2ma_C')
            quantity_disabled = False
            if quantity_input:
                quantity_disabled = quantity_input.get('disabled') is not None
                logger.info(f"Quantity input disabled: {quantity_disabled}")
                if quantity_disabled:
                    add_to_bag_available = False
            
            logger.info(f"Final availability decision: {add_to_bag_available}")
            
            return {
                'title': product_title,
                'available': add_to_bag_available,
                'parsed_successfully': True,
                'found_buttons': found_buttons
            }
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return {
                'title': 'Unknown Product',
                'available': False,
                'parsed_successfully': False,
                'found_buttons': []
            }

    async def debug_single_check(self):
        """Single debug check to see what's happening"""
        logger.info("🔍 Starting DEBUG mode - Single check")
        
        await self.create_session()
        
        try:
            logger.info(f"Fetching: {self.product_url}")
            html_content, status_code = await self.fetch_page(self.product_url)
            
            if not html_content:
                logger.error(f"Failed to fetch page (HTTP {status_code})")
                return
            
            logger.info(f"✅ Page fetched successfully (HTTP {status_code})")
            logger.info(f"📄 Content length: {len(html_content)} characters")
            
            # Run debug analysis
            self.debug_page_content(html_content)
            
            # Parse product info
            product_info = self.parse_product_info(html_content)
            
            print(f"\n🎯 FINAL RESULT:")
            print(f"   Product: {product_info['title']}")
            print(f"   Available: {product_info['available']}")
            print(f"   Buttons found: {len(product_info.get('found_buttons', []))}")
            
            # Send debug info via Telegram
            debug_message = f"""
🔍 <b>PopMart Debug Report</b>

📄 <b>Product:</b> {product_info['title']}
🔗 <b>URL:</b> {self.product_url}
📊 <b>HTTP Status:</b> {status_code}
📝 <b>Content Length:</b> {len(html_content)} chars
⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 <b>Availability:</b> {'✅ AVAILABLE' if product_info['available'] else '❌ NOT AVAILABLE'}

📋 <b>Buttons Found:</b> {len(product_info.get('found_buttons', []))}

🔧 Check console output and 'debug_page.html' for detailed analysis.
            """
            
            await self.send_telegram_message(debug_message.strip())
            
        finally:
            await self.close_session()

async def main():
    """Debug mode main function"""
    try:
        config_manager = ConfigManager("config.json")
        monitor = PopMartDebugMonitor(config_manager)
        
        print("🔍 PopMart Debug Monitor")
        print("This will run a single check and show detailed debug information.")
        print("Check console output and 'debug_page.html' file for full analysis.\n")
        
        await monitor.debug_single_check()
        
        print(f"\n✅ Debug check complete!")
        print(f"📁 Check 'debug_page.html' in the current directory for the full page content.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())