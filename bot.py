#!/usr/bin/env python3
"""
Popmart Labubu Product Monitor
Advanced monitoring script with Cloudflare bypass and Discord notifications
"""

import json
import time
import random
import logging
import requests
import cloudscraper
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc
from discord_webhook import DiscordWebhook, DiscordEmbed
import schedule
from datetime import datetime
import sys
import os
import threading
from fake_useragent import UserAgent

class PopmartMonitor:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.session = cloudscraper.create_scraper()
        self.driver = None
        self.ua = UserAgent()
        self.setup_logging()
        self.last_check_time = {}
        
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('popmart_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Config file {self.config_file} not found!")
            return self.create_default_config()

    def create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "discord_webhook_url": "",
            "account": {
                "email": "",
                "password": ""
            },
            "products": [
                {
                    "name": "LABUBU × PRONOUNCE - WINGS OF FORTUNE Vinyl Plush Hanging Card",
                    "url": "https://www.popmart.com/us/products/1584/LABUBU-%C3%97-PRONOUNCE---WINGS-OF-FORTUNE-Vinyl-Plush-Hanging-Card",
                    "target_price": 19.99,
                    "notify_price_changes": True
                }
            ],
            "monitoring": {
                "check_interval_minutes": 2,
                "max_check_interval_minutes": 5,
                "random_delay": True,
                "human_behavior": True
            },
            "cloudflare": {
                "max_retries": 3,
                "retry_delay": 10,
                "use_selenium_fallback": True
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        self.logger.info(f"Created default config file: {self.config_file}")
        self.logger.info("Please update the config file with your Discord webhook and account details!")
        return default_config

    def setup_selenium(self):
        """Setup undetected Chrome driver"""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f'--user-agent={self.ua.random}')
            
            # Headless mode for server deployment
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            
            self.driver = uc.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to setup Selenium driver: {e}")
            return False

    def human_behavior_delay(self):
        """Add random human-like delays"""
        if self.config.get('monitoring', {}).get('human_behavior', True):
            delay = random.uniform(1, 5)
            time.sleep(delay)

    def simulate_mouse_movement(self):
        """Simulate human mouse movements"""
        if self.driver and self.config.get('monitoring', {}).get('human_behavior', True):
            try:
                actions = ActionChains(self.driver)
                # Random mouse movements
                for _ in range(random.randint(1, 3)):
                    x = random.randint(100, 800)
                    y = random.randint(100, 600)
                    actions.move_by_offset(x, y).perform()
                    time.sleep(random.uniform(0.1, 0.5))
            except Exception:
                pass

    def send_discord_notification(self, title, description, color=0x00ff00, fields=None, image_url=None):
        """Send notification to Discord"""
        webhook_url = self.config.get('discord_webhook_url')
        if not webhook_url:
            self.logger.error("Discord webhook URL not configured!")
            return False

        try:
            webhook = DiscordWebhook(url=webhook_url)
            embed = DiscordEmbed(title=title, description=description, color=color)
            embed.set_timestamp()
            
            if fields:
                for field in fields:
                    embed.add_embed_field(
                        name=field.get('name', ''),
                        value=field.get('value', ''),
                        inline=field.get('inline', False)
                    )
            
            if image_url:
                embed.set_image(url=image_url)
            
            webhook.add_embed(embed)
            response = webhook.execute()
            
            if response.status_code == 200:
                self.logger.info(f"Discord notification sent: {title}")
                return True
            else:
                self.logger.error(f"Failed to send Discord notification: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Discord notification: {e}")
            return False

    def handle_cloudflare_challenge(self, url):
        """Handle Cloudflare challenges using multiple methods"""
        self.logger.info("Handling Cloudflare challenge...")
        
        # Method 1: CloudScraper
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200 and "cf-browser-verification" not in response.text.lower():
                return response
        except Exception as e:
            self.logger.warning(f"CloudScraper failed: {e}")

        # Method 2: Selenium with undetected-chromedriver
        if self.config.get('cloudflare', {}).get('use_selenium_fallback', True):
            try:
                if not self.driver:
                    if not self.setup_selenium():
                        return None
                
                self.driver.get(url)
                self.human_behavior_delay()
                
                # Wait for Cloudflare challenge to complete
                WebDriverWait(self.driver, 30).until(
                    lambda driver: "cf-browser-verification" not in driver.page_source.lower()
                )
                
                # Additional wait for page to fully load
                time.sleep(random.uniform(3, 7))
                
                return self.driver.page_source
                
            except TimeoutException:
                self.logger.error("Cloudflare challenge timeout")
            except Exception as e:
                self.logger.error(f"Selenium fallback failed: {e}")
        
        return None

    def extract_product_info(self, html_content, product_url):
        """Extract product information from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        product_info = {
            'name': '',
            'price': '',
            'in_stock': False,
            'image_url': '',
            'direct_buy_url': product_url
        }
        
        try:
            # Extract product name from title or meta tags
            title_tag = soup.find('title')
            if title_tag:
                product_info['name'] = title_tag.get_text().strip()
            
            # Check stock status - Key indicators
            stock_indicators = {
                'in_stock': [
                    'ADD TO BAG',
                    'index_red__kx6Ql',  # Red button class for add to bag
                    'ADD TO CART'
                ],
                'out_of_stock': [
                    'NOTIFY ME WHEN AVAILABLE',
                    'index_black__RgEgP',  # Black button class for notify
                    'Out of Stock',
                    'SOLD OUT'
                ]
            }
            
            page_text = html_content.lower()
            
            # Check for in-stock indicators
            for indicator in stock_indicators['in_stock']:
                if indicator.lower() in page_text:
                    product_info['in_stock'] = True
                    break
            
            # Check for out-of-stock indicators (override in_stock if found)
            for indicator in stock_indicators['out_of_stock']:
                if indicator.lower() in page_text:
                    product_info['in_stock'] = False
                    break
            
            # Extract price
            price_patterns = [
                r'\$[\d,]+\.?\d*',
                r'price["\s]*:[\s]*["\$]*([\d,]+\.?\d*)',
                r'[\$][\d,]+\.?\d*'
            ]
            
            import re
            for pattern in price_patterns:
                price_match = re.search(pattern, html_content, re.IGNORECASE)
                if price_match:
                    product_info['price'] = price_match.group(0)
                    break
            
            # Extract image URL
            img_tags = soup.find_all('img', {'alt': 'POP MART'})
            for img in img_tags:
                src = img.get('src', '')
                if 'popmart.com' in src and ('jpg' in src or 'png' in src or 'webp' in src):
                    product_info['image_url'] = src
                    break
            
        except Exception as e:
            self.logger.error(f"Error extracting product info: {e}")
        
        return product_info

    def check_product(self, product_config):
        """Check individual product availability"""
        product_url = product_config['url']
        product_name = product_config['name']
        
        self.logger.info(f"Checking product: {product_name}")
        
        max_retries = self.config.get('cloudflare', {}).get('max_retries', 3)
        retry_delay = self.config.get('cloudflare', {}).get('retry_delay', 10)
        
        for attempt in range(max_retries):
            try:
                # Add random delay between requests
                if attempt > 0:
                    time.sleep(retry_delay + random.uniform(1, 5))
                
                # Get page content
                content = self.handle_cloudflare_challenge(product_url)
                
                if content:
                    if isinstance(content, requests.Response):
                        html_content = content.text
                    else:
                        html_content = content
                    
                    # Extract product information
                    product_info = self.extract_product_info(html_content, product_url)
                    
                    # Check if product is now in stock
                    if product_info['in_stock']:
                        self.send_stock_notification(product_info, product_config)
                        return True
                    else:
                        self.logger.info(f"Product still out of stock: {product_name}")
                        return False
                        
                else:
                    self.logger.warning(f"Failed to get content for {product_name} (attempt {attempt + 1})")
                    
            except Exception as e:
                self.logger.error(f"Error checking product {product_name} (attempt {attempt + 1}): {e}")
                
                # Send error notification
                self.send_discord_notification(
                    title="🚨 Monitor Error",
                    description=f"Error checking product: {product_name}\nError: {str(e)}",
                    color=0xff0000
                )
        
        self.logger.error(f"Failed to check product after {max_retries} attempts: {product_name}")
        return False

    def send_stock_notification(self, product_info, product_config):
        """Send stock availability notification"""
        fields = [
            {
                'name': '💰 Price',
                'value': product_info.get('price', 'N/A'),
                'inline': True
            },
            {
                'name': '🔗 Direct Buy Link',
                'value': f"[BUY NOW]({product_info['direct_buy_url']})",
                'inline': True
            },
            {
                'name': '⏰ Time',
                'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'inline': True
            }
        ]
        
        self.send_discord_notification(
            title="🎉 PRODUCT IN STOCK!",
            description=f"**{product_info['name']}** is now available!",
            color=0x00ff00,
            fields=fields,
            image_url=product_info.get('image_url')
        )

    def monitor_products(self):
        """Monitor all configured products"""
        products = self.config.get('products', [])
        
        if not products:
            self.logger.warning("No products configured for monitoring!")
            return
        
        self.logger.info(f"Starting monitoring cycle for {len(products)} products...")
        
        for product in products:
            try:
                self.check_product(product)
                
                # Random delay between product checks
                if self.config.get('monitoring', {}).get('random_delay', True):
                    delay = random.uniform(10, 30)
                    time.sleep(delay)
                    
            except Exception as e:
                self.logger.error(f"Error in monitoring cycle: {e}")
                self.send_discord_notification(
                    title="🚨 Monitor Error",
                    description=f"Critical error in monitoring cycle: {str(e)}",
                    color=0xff0000
                )

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def run_monitor(self):
        """Main monitoring loop"""
        self.logger.info("🚀 Starting Popmart Monitor...")
        
        # Send startup notification
        self.send_discord_notification(
            title="🤖 Monitor Started",
            description="Popmart Labubu Monitor is now running!",
            color=0x0099ff
        )
        
        try:
            # Schedule monitoring
            interval = self.config.get('monitoring', {}).get('check_interval_minutes', 2)
            schedule.every(interval).minutes.do(self.monitor_products)
            
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check schedule every 30 seconds
                
        except KeyboardInterrupt:
            self.logger.info("Monitor stopped by user")
        except Exception as e:
            self.logger.error(f"Critical error in main loop: {e}")
            self.send_discord_notification(
                title="💀 Monitor Stopped",
                description=f"Monitor stopped due to critical error: {str(e)}",
                color=0xff0000
            )
        finally:
            self.cleanup()

if __name__ == "__main__":
    monitor = PopmartMonitor()
    monitor.run_monitor()