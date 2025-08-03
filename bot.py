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
                "password": "",
                "login_required": False
            },
            "products": [
                {
                    "name": "LABUBU × PRONOUNCE - WINGS OF FORTUNE Vinyl Plush Hanging Card",
                    "url": "https://www.popmart.com/us/products/1584/LABUBU-%C3%97-PRONOUNCE---WINGS-OF-FORTUNE-Vinyl-Plush-Hanging-Card"
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
        """Setup Chrome driver with multiple fallback strategies"""
        try:
            # Strategy 1: Try undetected-chromedriver with better settings
            try:
                self.logger.info("Attempting undetected-chromedriver setup...")
                
                options = uc.ChromeOptions()
                
                # Essential Chrome arguments for headless operation
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--disable-web-security')
                options.add_argument('--allow-running-insecure-content')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-plugins')
                options.add_argument('--disable-images')
                options.add_argument('--disable-default-apps')
                options.add_argument('--no-first-run')
                options.add_argument('--disable-background-timer-throttling')
                options.add_argument('--disable-renderer-backgrounding')
                options.add_argument('--disable-backgrounding-occluded-windows')
                
                # User agent rotation
                options.add_argument(f'--user-agent={self.ua.random}')
                
                # Try to create driver with timeout
                self.driver = uc.Chrome(
                    options=options, 
                    version_main=None,
                    driver_executable_path=None,
                    browser_executable_path=None,
                    port=0  # Let Chrome choose available port
                )
                
                # Quick test
                self.driver.set_page_load_timeout(30)
                self.driver.get("data:text/html,<html><body>Test</body></html>")
                
                self.logger.info("Undetected Chrome driver setup successful")
                return True
                
            except Exception as uc_error:
                self.logger.warning(f"Undetected Chrome failed: {uc_error}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
            
            # Strategy 2: Regular Selenium with WebDriver Manager
            try:
                self.logger.info("Trying regular Selenium with WebDriver Manager...")
                
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                from webdriver_manager.chrome import ChromeDriverManager
                
                chrome_options = ChromeOptions()
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-plugins')
                chrome_options.add_argument('--disable-images')
                chrome_options.add_argument('--no-first-run')
                chrome_options.add_argument(f'--user-agent={self.ua.random}')
                
                # Anti-detection measures
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)
                
                # Setup service with WebDriver Manager
                service = Service(ChromeDriverManager().install())
                
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_page_load_timeout(30)
                
                # Test the driver
                self.driver.get("data:text/html,<html><body>Test</body></html>")
                
                self.logger.info("Regular Chrome driver setup successful")
                return True
                
            except Exception as reg_error:
                self.logger.warning(f"Regular Selenium failed: {reg_error}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
            
            # Strategy 3: Try with system Chrome binary
            try:
                self.logger.info("Trying with system Chrome binary...")
                
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                
                chrome_options = ChromeOptions()
                chrome_options.binary_location = "/usr/bin/google-chrome"  # System Chrome
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--remote-debugging-port=9222')
                chrome_options.add_argument(f'--user-agent={self.ua.random}')
                
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(30)
                self.driver.get("data:text/html,<html><body>Test</body></html>")
                
                self.logger.info("System Chrome driver setup successful")
                return True
                
            except Exception as sys_error:
                self.logger.warning(f"System Chrome failed: {sys_error}")
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
            
            # Execute stealth scripts if we have a working driver
            if self.driver:
                try:
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                    self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
                except Exception:
                    pass
                return True
            
        except Exception as e:
            self.logger.error(f"All Chrome driver strategies failed: {e}")
        
        self.logger.error("Failed to setup any Chrome driver - will continue with CloudScraper only")
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
        """Handle Cloudflare challenges and 403 blocks using multiple methods"""
        self.logger.info(f"Fetching content from: {url}")
        
        # Method 1: Enhanced CloudScraper with rotating strategies
        for attempt in range(3):
            try:
                self.logger.info(f"CloudScraper attempt {attempt + 1}/3")
                
                # Create new scraper for each attempt
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'linux' if attempt == 0 else 'windows' if attempt == 1 else 'darwin',
                        'desktop': True
                    },
                    delay=random.uniform(1, 3),
                    debug=False
                )
                
                # Rotate headers for each attempt
                headers_sets = [
                    {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0',
                    },
                    {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'User-Agent': self.ua.random,
                    },
                    {
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Connection': 'keep-alive',
                        'User-Agent': self.ua.random,
                    }
                ]
                
                headers = headers_sets[attempt]
                
                # Add random delay between attempts
                if attempt > 0:
                    time.sleep(random.uniform(2, 5))
                
                response = scraper.get(url, headers=headers, timeout=30, allow_redirects=True)
                
                self.logger.info(f"CloudScraper response: {response.status_code}")
                
                if response.status_code == 200:
                    # Validate content quality
                    content_checks = [
                        len(response.text) > 1000,
                        "cf-browser-verification" not in response.text.lower(),
                        "checking your browser" not in response.text.lower(),
                        "popmart" in response.text.lower() or "labubu" in response.text.lower()
                    ]
                    
                    if all(content_checks[:2]) and any(content_checks[2:]):  # At least basic checks + one content check
                        self.logger.info("CloudScraper succeeded with valid content")
                        return response
                    else:
                        self.logger.warning(f"CloudScraper got low-quality content (length: {len(response.text)})")
                        
                elif response.status_code == 403:
                    self.logger.warning(f"CloudScraper blocked (403) - attempt {attempt + 1}")
                    # Try different scraper configuration on 403
                    continue
                    
                else:
                    self.logger.warning(f"CloudScraper returned status {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"CloudScraper attempt {attempt + 1} failed: {e}")
                continue

        # Method 2: Selenium approach (only if CloudScraper completely failed)
        if self.config.get('cloudflare', {}).get('use_selenium_fallback', True):
            self.logger.info("All CloudScraper attempts failed, trying Selenium...")
            
            try:
                # Setup driver if not already done
                if not self.driver:
                    self.logger.info("Setting up Selenium driver...")
                    if not self.setup_selenium():
                        self.logger.error("Could not setup any Selenium driver")
                        return self.try_simple_requests(url)
                
                # Navigate with error handling
                self.logger.info("Navigating to URL with Selenium...")
                self.driver.get(url)
                
                # Wait and check for challenges
                initial_wait = random.uniform(3, 6)
                time.sleep(initial_wait)
                
                max_wait = 45  # Increased timeout
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    try:
                        page_source = self.driver.page_source
                        
                        # Check challenge indicators
                        challenge_indicators = [
                            "cf-browser-verification",
                            "checking your browser", 
                            "please wait",
                            "ddos protection",
                            "security check"
                        ]
                        
                        in_challenge = any(indicator in page_source.lower() for indicator in challenge_indicators)
                        
                        if in_challenge:
                            self.logger.info(f"Selenium waiting for challenge... ({int(time.time() - start_time)}s)")
                            time.sleep(3)
                            continue
                        
                        # Check for valid content
                        if len(page_source) > 1000:
                            content_indicators = ["popmart", "labubu", "add to bag", "notify me when available"]
                            has_content = any(indicator in page_source.lower() for indicator in content_indicators)
                            
                            if has_content:
                                self.logger.info("Selenium succeeded - got valid Popmart content")
                                return page_source
                            elif "access denied" in page_source.lower() or "403" in page_source:
                                self.logger.error("Selenium got access denied")
                                break
                            else:
                                self.logger.warning("Selenium got content but quality unclear, waiting...")
                                time.sleep(2)
                                continue
                        
                        time.sleep(2)
                        
                    except Exception as e:
                        self.logger.warning(f"Error during Selenium wait: {e}")
                        break
                
                # Final attempt to get content
                try:
                    final_content = self.driver.page_source
                    if len(final_content) > 500:  # Accept minimal content as last resort
                        self.logger.warning("Selenium timeout, returning available content")
                        return final_content
                except Exception:
                    pass
                    
            except Exception as e:
                self.logger.error(f"Selenium approach completely failed: {e}")
                # Clean up broken driver
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
        
        # Method 3: Simple requests fallback
        return self.try_simple_requests(url)
    
    def try_simple_requests(self, url):
        """Try simple requests as absolute last resort"""
        try:
            self.logger.info("Trying simple requests as last resort...")
            
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            
            for ua in user_agents:
                headers = {
                    'User-Agent': ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
                
                response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
                
                if response.status_code == 200 and len(response.text) > 500:
                    self.logger.info(f"Simple requests worked with UA: {ua[:50]}...")
                    return response
                    
                time.sleep(random.uniform(1, 3))
                
        except Exception as e:
            self.logger.warning(f"Simple requests failed: {e}")
        
        self.logger.error("All content fetching methods failed")
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

    def handle_location_popup(self):
        """Handle United States location confirmation popup"""
        try:
            # Look for location popup: "You are in the United States.Update your location?"
            location_popup = self.driver.find_element(By.CLASS_NAME, "index_ipWarnContainer__d5qTd")
            if location_popup.is_displayed():
                self.logger.info("Location popup detected, closing it...")
                
                # Click the close button
                close_btn = self.driver.find_element(By.CLASS_NAME, "index_closeIcon__oBwY4")
                close_btn.click()
                self.human_behavior_delay()
                return True
        except Exception:
            pass
        return False

    def handle_privacy_policy(self):
        """Handle Privacy Policy and Terms & Conditions popup"""
        try:
            # Look for policy popup: "I agree to the Privacy Policy and Terms & Conditions"
            policy_popup = self.driver.find_element(By.CLASS_NAME, "policy_aboveFixedContainer__KfeZi")
            if policy_popup.is_displayed():
                self.logger.info("Privacy policy popup detected, accepting...")
                
                # Click ACCEPT button
                accept_btn = self.driver.find_element(By.CLASS_NAME, "policy_acceptBtn__ZNU71")
                accept_btn.click()
                self.human_behavior_delay()
                return True
        except Exception:
            pass
        return False

    def perform_login(self, email, password):
        """Perform complete login process with all steps"""
        try:
            self.logger.info("Starting login process...")
            
            # Step 1: Handle location popup if present
            self.handle_location_popup()
            
            # Step 2: Handle privacy policy if present
            self.handle_privacy_policy()
            
            # Step 3: Enter email address
            self.logger.info("Entering email address...")
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_input.clear()
            email_input.send_keys(email)
            self.human_behavior_delay()
            
            # Step 4: Check the service agreement checkbox
            self.logger.info("Checking service agreement...")
            try:
                checkbox = self.driver.find_element(By.CLASS_NAME, "ant-checkbox-input")
                if not checkbox.is_selected():
                    checkbox.click()
                    self.human_behavior_delay()
            except Exception as e:
                self.logger.warning(f"Could not find or click checkbox: {e}")
            
            # Step 5: Click CONTINUE button
            self.logger.info("Clicking continue button...")
            continue_btn = self.driver.find_element(By.CSS_SELECTOR, "button.ant-btn.ant-btn-primary.index_loginButton__O6r8l")
            continue_btn.click()
            self.human_behavior_delay()
            
            # Step 6: Wait for password page and enter password
            self.logger.info("Entering password...")
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            password_input.clear()
            password_input.send_keys(password)
            self.human_behavior_delay()
            
            # Step 7: Click SIGN IN button
            self.logger.info("Clicking sign in button...")
            signin_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'].ant-btn.ant-btn-primary.index_loginButton__O6r8l")
            signin_btn.click()
            
            # Step 8: Wait for login to complete and check for errors
            time.sleep(5)
            
            # Check for "Oops" error modal
            try:
                error_modal = self.driver.find_element(By.CLASS_NAME, "layout_wafErrorModalText__fzi48")
                if error_modal.is_displayed():
                    error_text = error_modal.text
                    self.logger.error(f"Login error detected: {error_text}")
                    
                    # Click OK button to dismiss error
                    ok_btn = self.driver.find_element(By.CLASS_NAME, "layout_wafErrorModalButton__yJdyc")
                    ok_btn.click()
                    return False
            except Exception:
                pass
            
            # Check if login was successful by looking for user-specific elements
            try:
                # Look for elements that appear after successful login
                WebDriverWait(self.driver, 10).until(
                    lambda driver: "index_disabledEmail__sdPjU" not in driver.page_source
                )
                self.logger.info("Login successful!")
                return True
            except TimeoutException:
                self.logger.error("Login appears to have failed - still on login page")
                return False
                
        except Exception as e:
            self.logger.error(f"Login process failed: {e}")
            return False

    def is_login_required(self, html_content):
        """Check if the page requires login using specific HTML elements"""
        login_indicators = [
            # Email input page
            'placeholder="Enter your e-mail address"',
            'class="ant-input index_loginInput__HBgjq"',
            'id="email"',
            
            # Password input page  
            'placeholder="Enter your password"',
            'id="password"',
            'class="index_disabledEmail__sdPjU"',
            
            # Login form
            'class="ant-form ant-form-horizontal index_loginForm__yLEpj"',
            
            # Login buttons
            'class="ant-btn ant-btn-primary index_loginButton__O6r8l"',
            
            # Service agreement checkbox
            'class="index_serviceCheck__D3US1"',
            'class="ant-checkbox-wrapper index_serviceCheckbox__KjCpl"',
            
            # Privacy policy popup
            'class="policy_aboveFixedContainer__KfeZi"',
            'class="policy_acceptBtn__ZNU71"',
            
            # Location popup
            'class="index_ipWarnContainer__d5qTd"',
            'You are in the United States'
        ]
        
        for indicator in login_indicators:
            if indicator in html_content:
                return True
        return False

    def handle_login_if_required(self, html_content):
        """Handle login process if required and account details are provided"""
        if not self.is_login_required(html_content):
            return True
        
        # Check if login is enabled in config
        account_config = self.config.get('account', {})
        if not account_config.get('login_required', False):
            self.logger.info("Login required but disabled in config - monitoring without login")
            return True
        
        email = account_config.get('email', '')
        password = account_config.get('password', '')
        
        if not email or not password:
            self.logger.warning("Login required but credentials not provided in config")
            return False
        
        # Ensure we have a Selenium driver for login
        if not self.driver:
            if not self.setup_selenium():
                return False
        
        return self.perform_login(email, password)

    def check_product(self, product_config):
        """Check individual product availability with login handling"""
        product_url = product_config['url']
        product_name = product_config['name']
        
        self.logger.info(f"Checking product: {product_name}")
        
        max_retries = self.config.get('cloudflare', {}).get('max_retries', 3) retry_delay = self.config.get('cloudflare', {}).get('retry_delay', 10)

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
                
                # Handle login if required
                if self.is_login_required(html_content):
                    self.logger.info("Login required for this product page")
                    
                    # If using Selenium driver, try to login
                    if self.driver:
                        login_success = self.handle_login_if_required(html_content)
                        if login_success:
                            # Get page content again after login
                            time.sleep(3)
                            html_content = self.driver.page_source
                        else:
                            self.logger.warning("Login failed, continuing with limited monitoring")
                
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

if name == "main": monitor = PopmartMonitor() monitor.run_monitor()