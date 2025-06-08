# backend/examples/screenshot_example.py

"""
Example script demonstrating screenshot capture functionality.

This script shows how to:
1. Initialize the screenshot service
2. Capture screenshots at different viewports
3. Handle results and file management
4. Use both sequential and concurrent capture modes

Usage:
    # Run the example
    python examples/screenshot_example.py
"""

import asyncio
import sys
from pathlib import Path
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.screenshot_service import ScreenshotService, ViewportType
from app.services.browser_manager import BrowserManager, BrowserType
from app.config import settings


async def demo_single_screenshot():
    """Demonstrate single screenshot capture."""
    print("📷 Single Screenshot Capture Demo")
    print("=" * 50)
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        service = ScreenshotService(browser_manager)
        
        # Get desktop viewport
        viewport = service.get_viewport_by_type(ViewportType.DESKTOP)
        
        print(f"Capturing screenshot at {viewport.name} ({viewport.width}x{viewport.height})")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Patch settings for this demo
            original_path = settings.temp_storage_path
            settings.temp_storage_path = temp_dir
            
            try:
                # Capture screenshot of a simple test page
                test_url = "data:text/html,<html><body style='background: linear-gradient(45deg, #ff6b6b, #4ecdc4); height: 100vh; display: flex; align-items: center; justify-content: center; font-family: Arial, sans-serif;'><h1 style='color: white; font-size: 3em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);'>Screenshot Test</h1></body></html>"
                
                result = await service.capture_screenshot(
                    url=test_url,
                    viewport=viewport,
                    session_id="demo-session",
                    wait_for_load=True,
                    full_page=True,
                    quality=90
                )
                
                if result.success:
                    print(f"✅ Screenshot captured successfully!")
                    print(f"   File: {Path(result.file_path).name}")
                    print(f"   Size: {result.file_size:,} bytes")
                    print(f"   Time: {result.capture_time:.2f}s")
                    print(f"   Page title: {result.page_title}")
                    if result.page_dimensions:
                        print(f"   Page dimensions: {result.page_dimensions[0]}x{result.page_dimensions[1]}")
                else:
                    print(f"❌ Screenshot failed: {result.error}")
                    
            finally:
                settings.temp_storage_path = original_path
    
    except Exception as e:
        print(f"💥 Demo failed: {str(e)}")
    
    finally:
        await browser_manager.cleanup()
        print("🧹 Cleanup completed")


async def demo_multi_viewport_screenshots():
    """Demonstrate multi-viewport screenshot capture."""
    print("\n📱💻 Multi-Viewport Screenshot Demo")
    print("=" * 50)
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        service = ScreenshotService(browser_manager)
        
        # Use default viewports (mobile, tablet, desktop, large desktop)
        viewports = service.get_default_viewports()
        
        print(f"Capturing screenshots at {len(viewports)} viewports:")
        for vp in viewports:
            print(f"  - {vp.name}: {vp.width}x{vp.height} (mobile: {vp.is_mobile})")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = settings.temp_storage_path
            settings.temp_storage_path = temp_dir
            
            try:
                # Create a responsive test page
                test_url = """data:text/html,
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {
                            margin: 0;
                            font-family: Arial, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            min-height: 100vh;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        }
                        .container {
                            text-align: center;
                            padding: 2rem;
                            border-radius: 15px;
                            background: rgba(255,255,255,0.1);
                            backdrop-filter: blur(10px);
                            border: 1px solid rgba(255,255,255,0.2);
                        }
                        h1 { font-size: 3rem; margin-bottom: 1rem; }
                        .viewport-info { font-size: 1.2rem; margin: 1rem 0; }
                        .responsive-grid {
                            display: grid;
                            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                            gap: 1rem;
                            margin-top: 2rem;
                        }
                        .card {
                            background: rgba(255,255,255,0.1);
                            padding: 1rem;
                            border-radius: 10px;
                            border: 1px solid rgba(255,255,255,0.1);
                        }
                        @media (max-width: 768px) {
                            h1 { font-size: 2rem; }
                            .container { padding: 1rem; }
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Responsive Test Page</h1>
                        <div class="viewport-info">Multi-Viewport Screenshot Demo</div>
                        <div class="responsive-grid">
                            <div class="card">📱 Mobile Optimized</div>
                            <div class="card">💻 Desktop Ready</div>
                            <div class="card">📐 Responsive Design</div>
                        </div>
                    </div>
                    <script>
                        // Add viewport dimensions to page
                        document.querySelector('.viewport-info').innerHTML += 
                            '<br>Viewport: ' + window.innerWidth + 'x' + window.innerHeight;
                    </script>
                </body>
                </html>
                """.replace('\n                ', '\n')
                
                print("\n🚀 Starting concurrent capture...")
                start_time = asyncio.get_event_loop().time()
                
                # Capture screenshots concurrently
                batch = await service.capture_multi_viewport_screenshots(
                    url=test_url,
                    session_id="multi-demo-session",
                    viewports=viewports,
                    concurrent=True,
                    max_concurrent=3,
                    wait_for_load=True,
                    full_page=True,
                    quality=85
                )
                
                end_time = asyncio.get_event_loop().time()
                
                print(f"\n📊 Capture Results:")
                print(f"   Total time: {batch.total_capture_time:.2f}s")
                print(f"   Wall clock time: {end_time - start_time:.2f}s")
                print(f"   Success rate: {batch.success_rate:.1f}%")
                print(f"   Successful: {len(batch.successful_screenshots)}")
                print(f"   Failed: {len(batch.failed_screenshots)}")
                
                print(f"\n📷 Individual Results:")
                for result in batch.screenshots:
                    status = "✅" if result.success else "❌"
                    print(f"   {status} {result.viewport.name}: {result.file_size:,} bytes in {result.capture_time:.2f}s")
                    if not result.success:
                        print(f"      Error: {result.error}")
                
                # Demonstrate screenshot info retrieval
                print(f"\n📋 Session Screenshot Info:")
                info = await service.get_screenshot_info("multi-demo-session")
                print(f"   Screenshots: {info['screenshot_count']}")
                print(f"   Total size: {info['total_size']:,} bytes")
                
                # Show file details
                for screenshot_info in info['screenshots']:
                    print(f"   - {screenshot_info['filename']}: {screenshot_info['size']:,} bytes")
                    
            finally:
                settings.temp_storage_path = original_path
    
    except Exception as e:
        print(f"💥 Demo failed: {str(e)}")
    
    finally:
        await browser_manager.cleanup()
        print("🧹 Cleanup completed")


async def demo_custom_viewports():
    """Demonstrate custom viewport creation."""
    print("\n🎨 Custom Viewport Demo")
    print("=" * 50)
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        service = ScreenshotService(browser_manager)
        
        # Create custom viewports for specific use cases
        custom_viewports = [
            service.create_custom_viewport(
                name="Ultrawide Monitor",
                width=3440,
                height=1440,
                device_scale_factor=1.0,
                is_mobile=False
            ),
            service.create_custom_viewport(
                name="Portrait Tablet",
                width=768,
                height=1024,
                device_scale_factor=2.0,
                is_mobile=False
            ),
            service.create_custom_viewport(
                name="Small Mobile",
                width=320,
                height=568,
                device_scale_factor=2.0,
                is_mobile=True,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15"
            )
        ]
        
        print("Custom viewports created:")
        for vp in custom_viewports:
            print(f"  - {vp.name}: {vp.width}x{vp.height} (scale: {vp.device_scale_factor}x)")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = settings.temp_storage_path
            settings.temp_storage_path = temp_dir
            
            try:
                # Simple test page that shows viewport info
                test_url = """data:text/html,
                <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {
                            margin: 0;
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            background: linear-gradient(45deg, #FF512F, #F09819);
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        }
                        .info-card {
                            background: rgba(255,255,255,0.15);
                            border-radius: 20px;
                            padding: 2rem;
                            backdrop-filter: blur(15px);
                            border: 1px solid rgba(255,255,255,0.3);
                            text-align: center;
                            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                        }
                        h1 { font-size: 2.5rem; margin-bottom: 1rem; }
                        .metric { font-size: 1.1rem; margin: 0.5rem 0; }
                        .user-agent { font-size: 0.8rem; opacity: 0.8; margin-top: 1rem; word-break: break-all; }
                    </style>
                </head>
                <body>
                    <div class="info-card">
                        <h1>Custom Viewport Test</h1>
                        <div class="metric">Screen: <span id="screen"></span></div>
                        <div class="metric">Window: <span id="window"></span></div>
                        <div class="metric">Pixel Ratio: <span id="ratio"></span></div>
                        <div class="metric">Mobile: <span id="mobile"></span></div>
                        <div class="user-agent">UA: <span id="ua"></span></div>
                    </div>
                    <script>
                        document.getElementById('screen').textContent = screen.width + 'x' + screen.height;
                        document.getElementById('window').textContent = window.innerWidth + 'x' + window.innerHeight;
                        document.getElementById('ratio').textContent = window.devicePixelRatio;
                        document.getElementById('mobile').textContent = /Mobi|Android/i.test(navigator.userAgent) ? 'Yes' : 'No';
                        document.getElementById('ua').textContent = navigator.userAgent;
                    </script>
                </body>
                </html>
                """.replace('\n                ', '\n')
                
                print(f"\n🚀 Capturing custom viewport screenshots...")
                
                # Capture screenshots sequentially to see individual timing
                batch = await service.capture_multi_viewport_screenshots(
                    url=test_url,
                    session_id="custom-demo-session",
                    viewports=custom_viewports,
                    concurrent=False,  # Sequential for clearer timing
                    wait_for_load=True,
                    full_page=False,  # Just viewport size for custom viewports
                    quality=95
                )
                
                print(f"\n📊 Custom Viewport Results:")
                for i, result in enumerate(batch.screenshots):
                    viewport = custom_viewports[i]
                    status = "✅" if result.success else "❌"
                    print(f"   {status} {viewport.name}:")
                    print(f"      Dimensions: {viewport.width}x{viewport.height}")
                    print(f"      File size: {result.file_size:,} bytes")
                    print(f"      Capture time: {result.capture_time:.2f}s")
                    if result.page_title:
                        print(f"      Page title: {result.page_title}")
                    if not result.success:
                        print(f"      Error: {result.error}")
                    print()
                    
            finally:
                settings.temp_storage_path = original_path
    
    except Exception as e:
        print(f"💥 Demo failed: {str(e)}")
    
    finally:
        await browser_manager.cleanup()
        print("🧹 Cleanup completed")


async def demo_error_handling():
    """Demonstrate error handling in screenshot capture."""
    print("\n🚨 Error Handling Demo")
    print("=" * 50)
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        service = ScreenshotService(browser_manager)
        
        # Test with invalid URL
        print("Testing invalid URL...")
        viewport = service.get_viewport_by_type(ViewportType.DESKTOP)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = settings.temp_storage_path
            settings.temp_storage_path = temp_dir
            
            try:
                result = await service.capture_screenshot(
                    url="https://this-domain-definitely-does-not-exist-12345.com",
                    viewport=viewport,
                    session_id="error-demo-session"
                )
                
                if result.success:
                    print("   ⚠️  Unexpectedly succeeded")
                else:
                    print(f"   ✅ Correctly failed: {result.error}")
                
                # Test with very large viewport (might fail due to memory constraints)
                print("\nTesting extremely large viewport...")
                huge_viewport = service.create_custom_viewport(
                    name="Huge",
                    width=10000,
                    height=10000
                )
                
                result = await service.capture_screenshot(
                    url="data:text/html,<html><body><h1>Large viewport test</h1></body></html>",
                    viewport=huge_viewport,
                    session_id="error-demo-session"
                )
                
                if result.success:
                    print(f"   ✅ Large viewport succeeded: {result.file_size:,} bytes")
                else:
                    print(f"   ⚠️  Large viewport failed: {result.error}")
                    
            finally:
                settings.temp_storage_path = original_path
    
    except Exception as e:
        print(f"💥 Demo failed: {str(e)}")
    
    finally:
        await browser_manager.cleanup()
        print("🧹 Cleanup completed")


async def demo_cleanup_functionality():
    """Demonstrate cleanup functionality."""
    print("\n🧹 Cleanup Demo")
    print("=" * 50)
    
    browser_manager = BrowserManager(BrowserType.AUTO)
    
    try:
        await browser_manager.initialize()
        service = ScreenshotService(browser_manager)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = settings.temp_storage_path
            settings.temp_storage_path = temp_dir
            
            try:
                # Create some test screenshots
                test_url = "data:text/html,<html><body><h1>Cleanup Test</h1></body></html>"
                viewport = service.get_viewport_by_type(ViewportType.DESKTOP)
                
                print("Creating test screenshots...")
                for i in range(3):
                    result = await service.capture_screenshot(
                        url=test_url,
                        viewport=viewport,
                        session_id=f"cleanup-session-{i}"
                    )
                    if result.success:
                        print(f"   Created: {Path(result.file_path).name}")
                
                # Show current state
                info = await service.get_screenshot_info("cleanup-session-0")
                print(f"\nBefore cleanup - Session 0: {info['screenshot_count']} files")
                
                # Cleanup specific session
                cleaned = await service.cleanup_screenshots(session_id="cleanup-session-0")
                print(f"Cleaned up session 0: {cleaned} files")
                
                # Verify cleanup
                info = await service.get_screenshot_info("cleanup-session-0")
                print(f"After cleanup - Session 0: {info['screenshot_count']} files")
                
                # Cleanup all remaining
                cleaned = await service.cleanup_screenshots()
                print(f"Cleaned up all remaining: {cleaned} files")
                
            finally:
                settings.temp_storage_path = original_path
    
    except Exception as e:
        print(f"💥 Demo failed: {str(e)}")
    
    finally:
        await browser_manager.cleanup()
        print("🧹 Cleanup completed")


async def main():
    """Run all screenshot demos."""
    print("📸 Screenshot Service Demo")
    print("=" * 70)
    print()
    
    try:
        await demo_single_screenshot()
        await demo_multi_viewport_screenshots()
        await demo_custom_viewports()
        await demo_error_handling()
        await demo_cleanup_functionality()
        
        print("\n" + "=" * 70)
        print("🎉 All demos completed successfully!")
        print("\nKey features demonstrated:")
        print("✅ Single screenshot capture")
        print("✅ Multi-viewport concurrent capture")
        print("✅ Custom viewport creation")
        print("✅ Error handling and recovery")
        print("✅ File management and cleanup")
        print("✅ Responsive design testing")
        
    except KeyboardInterrupt:
        print("\n🛑 Demos interrupted by user")
    except Exception as e:
        print(f"\n💥 Demos failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())