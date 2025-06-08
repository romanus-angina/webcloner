# backend/examples/cloud_browser_example.py

"""
Example script demonstrating cloud browser integration with Browserbase.

This script shows how to:
1. Configure cloud browser service
2. Use the browser manager for automatic fallback
3. Perform basic web automation tasks
4. Handle errors gracefully

Usage:
    # Set environment variables first
    export BROWSERBASE_API_KEY="your-api-key"
    export BROWSERBASE_PROJECT_ID="your-project-id"
    export USE_CLOUD_BROWSER=true
    
    # Run the example
    python examples/cloud_browser_example.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.browser_manager import BrowserManager, BrowserType
from app.services.cloud_browser import CloudBrowserService
from app.config import settings


async def test_cloud_browser_direct():
    """Test cloud browser service directly."""
    print("Testing CloudBrowserService directly...")
    
    service = CloudBrowserService()
    
    try:
        await service.initialize()
        print("✅ Cloud browser initialized successfully")
        
        # Get session info
        info = await service.get_session_info()
        print(f"📊 Session info: {info['session_id'][:8]}...")
        
        # Test page creation and navigation
        async with service.page_context() as page:
            print("🌐 Navigating to test page...")
            await page.goto("https://httpbin.org/status/200")
            
            title = await page.title()
            url = page.url
            print(f"📄 Page title: '{title}'")
            print(f"🔗 Current URL: {url}")
            
        print("✅ Cloud browser test completed successfully")
        
    except Exception as e:
        print(f"❌ Cloud browser test failed: {str(e)}")
        
    finally:
        await service.cleanup()
        print("🧹 Cloud browser cleaned up")


async def test_browser_manager_auto():
    """Test browser manager with automatic service selection."""
    print("\nTesting BrowserManager with auto-selection...")
    
    manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await manager.initialize()
        
        # Get service info
        info = await manager.get_service_info()
        service_type = info.get('service_type', 'unknown')
        print(f"✅ Browser manager initialized with {service_type} browser")
        
        # Test health check
        health = await manager.health_check()
        if health['healthy']:
            print("💚 Browser service is healthy")
        else:
            print(f"💔 Browser service unhealthy: {health.get('error', 'Unknown error')}")
        
        # Test basic automation
        async with manager.page_context() as page:
            print("🌐 Testing page automation...")
            await page.goto("data:text/html,<html><body><h1>Test Page</h1></body></html>")
            
            # Get page content
            content = await page.content()
            if "Test Page" in content:
                print("✅ Page content retrieved successfully")
            else:
                print("❌ Page content not as expected")
        
        print(f"✅ Browser manager test completed with {service_type} browser")
        
    except Exception as e:
        print(f"❌ Browser manager test failed: {str(e)}")
        
    finally:
        await manager.cleanup()
        print("🧹 Browser manager cleaned up")


async def test_fallback_scenario():
    """Test cloud-to-local fallback scenario."""
    print("\nTesting fallback scenario...")
    
    # Force cloud browser first, then test fallback
    manager = BrowserManager(BrowserType.CLOUD)
    
    try:
        await manager.initialize()
        service_type = manager._service_type.value if manager._service_type else "unknown"
        print(f"✅ Initialized with {service_type} browser")
        
        # If we got local browser, fallback already happened during init
        if service_type == "local":
            print("🔄 Automatic fallback to local browser occurred during initialization")
        
        # Test functionality regardless of service type
        async with manager.page_context() as page:
            await page.goto("https://httpbin.org/json")
            content = await page.content()
            if "application/json" in content or "slideshow" in content:
                print("✅ JSON test page loaded successfully")
        
    except Exception as e:
        print(f"❌ Fallback test failed: {str(e)}")
        # This is expected if neither cloud nor local browser can initialize
        
    finally:
        await manager.cleanup()


async def demonstrate_configuration():
    """Demonstrate different configuration scenarios."""
    print("\nDemonstrating configuration scenarios...")
    
    # Show current configuration
    print("Current configuration:")
    print(f"  USE_CLOUD_BROWSER: {getattr(settings, 'USE_CLOUD_BROWSER', False)}")
    print(f"  BROWSERBASE_API_KEY: {'✅ Set' if getattr(settings, 'BROWSERBASE_API_KEY', None) else '❌ Not set'}")
    print(f"  BROWSERBASE_PROJECT_ID: {'✅ Set' if getattr(settings, 'BROWSERBASE_PROJECT_ID', None) else '❌ Not set'}")
    print(f"  BROWSER_TYPE: {getattr(settings, 'BROWSER_TYPE', 'chromium')}")
    print(f"  BROWSER_HEADLESS: {getattr(settings, 'BROWSER_HEADLESS', True)}")
    
    # Test different browser manager configurations
    test_configs = [
        (BrowserType.AUTO, "Auto-selection"),
        (BrowserType.LOCAL, "Explicit local"),
        (BrowserType.CLOUD, "Explicit cloud")
    ]
    
    for browser_type, description in test_configs:
        print(f"\n🔧 Testing {description}...")
        manager = BrowserManager(browser_type)
        
        try:
            # Just test service selection logic without full initialization
            selected_type = manager._determine_browser_type()
            print(f"   Would select: {selected_type.value} browser")
            
        except Exception as e:
            print(f"   Configuration test failed: {str(e)}")


async def main():
    """Run all example tests."""
    print("🚀 Cloud Browser Integration Examples")
    print("=" * 50)
    
    # Check if cloud browser is configured
    cloud_configured = (
        getattr(settings, 'BROWSERBASE_API_KEY', None) and 
        getattr(settings, 'BROWSERBASE_PROJECT_ID', None)
    )
    
    if cloud_configured:
        print("☁️  Cloud browser appears to be configured")
        
        # Test cloud browser directly
        await test_cloud_browser_direct()
    else:
        print("⚠️  Cloud browser not configured - skipping direct cloud tests")
        print("   Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID to test cloud features")
    
    # Test browser manager (should work with any configuration)
    await test_browser_manager_auto()
    
    # Test fallback scenario
    await test_fallback_scenario()
    
    # Show configuration
    await demonstrate_configuration()
    
    print("\n" + "=" * 50)
    print("🎉 Examples completed!")


if __name__ == "__main__":
    # Set up environment for testing if not already configured
    if not os.getenv('BROWSERBASE_API_KEY'):
        print("💡 Tip: Set environment variables for full cloud browser testing:")
        print("   export BROWSERBASE_API_KEY='your-api-key'")
        print("   export BROWSERBASE_PROJECT_ID='your-project-id'")
        print("   export USE_CLOUD_BROWSER=true")
        print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Examples interrupted by user")
    except Exception as e:
        print(f"\n💥 Examples failed with error: {str(e)}")
        import traceback
        traceback.print_exc()