#!/usr/bin/env python3
"""
System Check Script for Popmart Monitor
Diagnoses common issues and provides fixes
"""

import subprocess
import sys
import os
import json
import requests
from pathlib import Path

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_chrome_installation():
    """Check if Chrome is properly installed"""
    print("🔍 Checking Chrome installation...")
    
    # Check for Chrome binary
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/opt/google/chrome/chrome"
    ]
    
    chrome_found = False
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"✅ Chrome found at: {path}")
            chrome_found = True
            
            # Check version
            success, version, error = run_command(f"{path} --version")
            if success:
                print(f"   Version: {version}")
            break
    
    if not chrome_found:
        print("❌ Chrome not found!")
        print("🔧 Fix: sudo apt update && sudo apt install google-chrome-stable")
        return False
    
    return True

def check_python_packages():
    """Check if required Python packages are installed"""
    print("\n🔍 Checking Python packages...")
    
    required_packages = [
        'requests', 'cloudscraper', 'beautifulsoup4', 'selenium', 
        'undetected-chromedriver', 'discord-webhook', 'schedule', 
        'fake-useragent', 'lxml', 'webdriver-manager'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n🔧 Fix: pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_config_file():
    """Check if config.json exists and is valid"""
    print("\n🔍 Checking configuration file...")
    
    if not os.path.exists('config.json'):
        print("❌ config.json not found!")
        print("🔧 Fix: Create config.json file with your settings")
        return False
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Check required fields
        required_fields = ['discord_webhook_url', 'products']
        for field in required_fields:
            if field not in config:
                print(f"❌ Missing required field: {field}")
                return False
            elif not config[field]:
                print(f"⚠️  Empty field: {field}")
        
        print("✅ config.json is valid")
        print(f"   Products to monitor: {len(config.get('products', []))}")
        print(f"   Discord webhook: {'configured' if config.get('discord_webhook_url') else 'missing'}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ config.json is invalid JSON: {e}")
        return False

def test_discord_webhook():
    """Test Discord webhook connectivity"""
    print("\n🔍 Testing Discord webhook...")
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        webhook_url = config.get('discord_webhook_url')
        if not webhook_url or webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
            print("⚠️  Discord webhook not configured")
            return False
        
        # Test webhook
        from discord_webhook import DiscordWebhook
        webhook = DiscordWebhook(url=webhook_url)
        webhook.content = "🧪 Test message from Popmart Monitor system check"
        response = webhook.execute()
        
        if hasattr(response, 'status_code') and response.status_code == 200:
            print("✅ Discord webhook working!")
            return True
        else:
            print("❌ Discord webhook failed")
            return False
            
    except Exception as e:
        print(f"❌ Discord webhook error: {e}")
        return False

def test_popmart_access():
    """Test access to Popmart website"""
    print("\n🔍 Testing Popmart website access...")
    
    test_url = "https://www.popmart.com/us/products/1584/LABUBU-%C3%97-PRONOUNCE---WINGS-OF-FORTUNE-Vinyl-Plush-Hanging-Card"
    
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        response = scraper.get(test_url, timeout=30)
        
        if response.status_code == 200:
            if len(response.text) > 1000:
                print("✅ Popmart access working with CloudScraper!")
                print(f"   Response length: {len(response.text)} characters")
                return True
            else:
                print(f"⚠️  Got response but content too short: {len(response.text)} characters")
        else:
            print(f"❌ HTTP {response.status_code}: {response.reason}")
            
    except Exception as e:
        print(f"❌ Popmart access failed: {e}")
        
    return False

def main():
    """Main system check function"""
    print("🤖 Popmart Monitor System Check")
    print("=" * 50)
    
    checks = [
        ("Chrome Installation", check_chrome_installation),
        ("Python Packages", check_python_packages),
        ("Configuration File", check_config_file),
        ("Discord Webhook", test_discord_webhook),
        ("Popmart Access", test_popmart_access)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check crashed: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n📊 SYSTEM CHECK SUMMARY")
    print("=" * 50)
    
    passed = 0
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {check_name}")
        if result:
            passed += 1
    
    print(f"\nScore: {passed}/{len(results)} checks passed")
    
    if passed == len(results):
        print("🎉 All checks passed! Your system should work perfectly.")
    elif passed >= len(results) * 0.7:
        print("⚠️  Most checks passed. Minor issues may affect performance.")
    else:
        print("❌ Multiple issues detected. Please fix the failed checks.")

if __name__ == "__main__":
    main()