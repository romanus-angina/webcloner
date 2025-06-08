# backend/tests/test_cloud_browser_integration.py

"""
Integration tests for cloud browser services.

These tests require actual external services and configuration:
- Browserbase API credentials (for cloud browser tests)
- Internet connectivity
- Real browser installations

Run with: pytest tests/test_cloud_browser_integration.py -v
Or: pytest -m integration
"""

import pytest
import asyncio
import os
from pathlib import Path

from app.services.cloud_browser import CloudBrowserService
from app.services.browser_manager import BrowserManager, BrowserType
from app.config import settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cloud_browser_integration():
    """
    Integration test for cloud browser service.
    Requires valid Browserbase configuration.
    """
    # Skip if not configured
    if not (hasattr(settings, 'BROWSERBASE_API_KEY') and settings.BROWSERBASE_API_KEY):
        pytest.skip("Browserbase not configured for integration tests")
    
    service = CloudBrowserService()
    
    try:
        print("🚀 Testing cloud browser initialization...")
        await service.initialize()
        
        info = await service.get_session_info()
        assert info["status"] == "connected"
        assert info["browser_connected"] is True
        print("✅ Cloud browser connected successfully")
        
        # Test basic page creation and navigation
        print("🌐 Testing page automation...")
        async with service.page_context() as page:
            await page.goto("data:text/html,<html><body><h1>Integration Test</h1></body></html>")
            
            # Verify page content
            content = await page.content()
            assert "Integration Test" in content
            print("✅ Page automation working")
            
        print("✅ Cloud browser integration test passed")
            
    except Exception as e:
        pytest.fail(f"Cloud browser integration failed: {str(e)}")
        
    finally:
        await service.cleanup()
        print("🧹 Cloud browser cleaned up")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_manager_auto_selection():
    """
    Integration test for browser manager with automatic service selection.
    Tests the actual decision-making logic with real configuration.
    """
    manager = BrowserManager(BrowserType.AUTO)
    
    try:
        print("🤖 Testing browser manager auto-selection...")
        await manager.initialize()
        
        # Test that some browser service is working
        info = await manager.get_service_info()
        assert info["manager_status"] == "initialized"
        assert info["service_type"] in ["local", "cloud"]
        
        service_type = info["service_type"]
        print(f"✅ Auto-selected {service_type} browser")
        
        # Test health check
        health = await manager.health_check()
        assert health["healthy"] is True
        print("💚 Browser service health check passed")
        
        # Test basic functionality
        print("🌐 Testing basic browser functionality...")
        async with manager.page_context() as page:
            await page.goto("data:text/html,<html><body><h1>Manager Test</h1></body></html>")
            content = await page.content()
            assert "Manager Test" in content
            print("✅ Browser functionality working")
            
    except Exception as e:
        pytest.fail(f"Browser manager integration failed: {str(e)}")
        
    finally:
        await manager.cleanup()
        print("🧹 Browser manager cleaned up")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cloud_browser_fallback_scenario():
    """
    Integration test for cloud-to-local fallback scenario.
    Tests what happens when cloud browser is requested but may not be available.
    """
    # Force attempt cloud browser first
    manager = BrowserManager(BrowserType.CLOUD)
    
    try:
        print("☁️ Testing cloud browser with potential fallback...")
        await manager.initialize()
        
        # Should have initialized with SOME browser (cloud or local fallback)
        info = await manager.get_service_info()
        assert info["manager_status"] == "initialized"
        assert info["service_type"] in ["local", "cloud"]
        
        service_type = info["service_type"]
        if service_type == "local":
            print("🔄 Successfully fell back to local browser")
        else:
            print("☁️ Successfully used cloud browser")
        
        # Test basic functionality works regardless of which service
        print("🌐 Testing cross-service compatibility...")
        async with manager.page_context() as page:
            # Use a real URL to test actual network capability
            await page.goto("https://httpbin.org/status/200")
            
            # Verify navigation worked
            url = page.url
            assert "httpbin.org" in url
            print(f"✅ Successfully navigated to {url}")
        
    except Exception as e:
        pytest.fail(f"Fallback scenario failed: {str(e)}")
        
    finally:
        await manager.cleanup()
        print("🧹 Fallback test cleaned up")


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_browser_manager_health_monitoring():
    """
    Integration test for browser manager health monitoring.
    Tests real health check functionality with actual browser services.
    """
    manager = BrowserManager(BrowserType.AUTO)
    
    try:
        print("🏥 Testing health monitoring...")
        
        # Test health before initialization
        health_before = await manager.health_check()
        assert health_before["healthy"] is False
        print("✅ Health check correctly reports unhealthy before init")
        
        # Initialize and test health after
        await manager.initialize()
        health_after = await manager.health_check()
        assert health_after["healthy"] is True
        assert health_after["service_type"] in ["local", "cloud"]
        print(f"✅ Health check reports healthy after init ({health_after['service_type']})")
        
        # Test service info
        info = await manager.get_service_info()
        assert "service_info" in info
        assert "manager_status" in info
        print("✅ Service info provides detailed status")
        
        # Test actual browser operation to verify health
        print("🔬 Verifying health with actual browser operation...")
        async with manager.page_context() as page:
            await page.goto("about:blank")
            title = await page.title()
            # about:blank should work on any browser
            print("✅ Browser operation confirms healthy status")
        
    except Exception as e:
        pytest.fail(f"Health monitoring test failed: {str(e)}")
        
    finally:
        await manager.cleanup()
        print("🧹 Health monitoring test cleaned up")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_browser_performance_benchmark():
    """
    Integration test that benchmarks browser performance.
    Useful for detecting performance regressions.
    """
    import time
    
    manager = BrowserManager(BrowserType.AUTO)
    
    try:
        print("⚡ Running performance benchmark...")
        
        # Measure initialization time
        start_time = time.time()
        await manager.initialize()
        init_time = time.time() - start_time
        
        print(f"📊 Initialization time: {init_time:.2f}s")
        assert init_time < 30.0, f"Initialization too slow: {init_time:.2f}s"
        
        # Measure page creation time
        start_time = time.time()
        async with manager.page_context() as page:
            page_creation_time = time.time() - start_time
            
            # Measure navigation time
            start_time = time.time()
            await page.goto("https://httpbin.org/status/200")
            navigation_time = time.time() - start_time
            
        print(f"📊 Page creation time: {page_creation_time:.2f}s")
        print(f"📊 Navigation time: {navigation_time:.2f}s")
        
        # Basic performance assertions
        assert page_creation_time < 10.0, f"Page creation too slow: {page_creation_time:.2f}s"
        assert navigation_time < 15.0, f"Navigation too slow: {navigation_time:.2f}s"
        
        print("✅ Performance within acceptable limits")
        
    except Exception as e:
        pytest.fail(f"Performance benchmark failed: {str(e)}")
        
    finally:
        await manager.cleanup()


# Configuration validation helpers
def test_integration_environment():
    """
    Test that integration test environment is properly configured.
    This is a regular test (not async) that validates the setup.
    """
    print("🔧 Checking integration test environment...")
    
    # Check if Browserbase is configured
    browserbase_configured = (
        hasattr(settings, 'BROWSERBASE_API_KEY') and settings.BROWSERBASE_API_KEY and
        hasattr(settings, 'BROWSERBASE_PROJECT_ID') and settings.BROWSERBASE_PROJECT_ID
    )
    
    if browserbase_configured:
        print("☁️ Browserbase configuration detected")
        print(f"   API Key: {'✅ Set' if settings.BROWSERBASE_API_KEY else '❌ Missing'}")
        print(f"   Project ID: {'✅ Set' if settings.BROWSERBASE_PROJECT_ID else '❌ Missing'}")
    else:
        print("⚠️ Browserbase not configured - cloud browser tests will be skipped")
    
    # Check browser settings
    print(f"🌐 Browser configuration:")
    print(f"   Type: {getattr(settings, 'BROWSER_TYPE', 'chromium')}")
    print(f"   Headless: {getattr(settings, 'BROWSER_HEADLESS', True)}")
    print(f"   Use Cloud: {getattr(settings, 'USE_CLOUD_BROWSER', False)}")
    
    # This test always passes - it's just informational
    assert True, "Environment check completed"


if __name__ == "__main__":
    """
    Allow running integration tests directly.
    
    Usage:
        python tests/test_cloud_browser_integration.py
    """
    pytest.main([__file__, "-v"])