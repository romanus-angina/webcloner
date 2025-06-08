import pytest
import os
from unittest.mock import patch
import importlib

from app.config import Settings
from app.services.cloud_browser import CloudBrowserService
from app.services.browser_manager import BrowserManager, BrowserType
from app.core.exceptions import ConfigurationError

class TestBrowserConfiguration:
    """Test suite for browser configuration validation."""
    
    def test_local_browser_configuration(self):
        with patch.dict(os.environ, {
            'BROWSER_TYPE': 'chromium',
            'BROWSER_HEADLESS': 'true',
            'BROWSER_TIMEOUT': '30',
            'USE_CLOUD_BROWSER': 'false'
        }, clear=True):
            settings = Settings()
            assert settings.BROWSER_TYPE == 'chromium'
            assert settings.BROWSER_HEADLESS is True
            assert settings.BROWSER_TIMEOUT == 30
            assert settings.USE_CLOUD_BROWSER is False
    
    def test_cloud_browser_configuration_complete(self):
        with patch.dict(os.environ, {
            'USE_CLOUD_BROWSER': 'true',
            'BROWSERBASE_API_KEY': 'test-api-key',
            'BROWSERBASE_PROJECT_ID': 'test-project-id'
        }, clear=True):
            settings = Settings()
            assert settings.USE_CLOUD_BROWSER is True
            assert settings.BROWSERBASE_API_KEY == 'test-api-key'
            assert settings.BROWSERBASE_PROJECT_ID == 'test-project-id'
    
    def test_cloud_browser_configuration_missing_api_key(self):
        service = CloudBrowserService()
        with patch('app.services.cloud_browser.settings') as mock_settings:
            mock_settings.BROWSERBASE_API_KEY = None
            mock_settings.BROWSERBASE_PROJECT_ID = 'test-project'
            with pytest.raises(ConfigurationError, match="API key not configured"):
                service._validate_configuration()
    
    def test_cloud_browser_configuration_missing_project_id(self):
        service = CloudBrowserService()
        with patch('app.services.cloud_browser.settings') as mock_settings:
            mock_settings.BROWSERBASE_API_KEY = 'test-key'
            mock_settings.BROWSERBASE_PROJECT_ID = None
            with pytest.raises(ConfigurationError, match="project ID not configured"):
                service._validate_configuration()
    
    def test_browser_manager_auto_selection_cloud(self):
        manager = BrowserManager(BrowserType.AUTO)
        with patch('app.services.browser_manager.settings') as mock_settings:
            mock_settings.USE_CLOUD_BROWSER = True
            mock_settings.BROWSERBASE_API_KEY = 'test-key'
            mock_settings.BROWSERBASE_PROJECT_ID = 'test-project'
            browser_type = manager._determine_browser_type()
            assert browser_type == BrowserType.CLOUD
    
    def test_browser_manager_auto_selection_local_fallback(self):
        manager = BrowserManager(BrowserType.AUTO)
        with patch('app.services.browser_manager.settings') as mock_settings:
            mock_settings.USE_CLOUD_BROWSER = True
            mock_settings.BROWSERBASE_API_KEY = None
            mock_settings.BROWSERBASE_PROJECT_ID = 'test-project'
            browser_type = manager._determine_browser_type()
            assert browser_type == BrowserType.LOCAL
    
    def test_browser_manager_explicit_selection(self):
        manager_local = BrowserManager(BrowserType.LOCAL)
        assert manager_local._determine_browser_type() == BrowserType.LOCAL
        manager_cloud = BrowserManager(BrowserType.CLOUD)
        assert manager_cloud._determine_browser_type() == BrowserType.CLOUD
    
    def test_viewport_configuration(self):
        with patch.dict(os.environ, {
            'BROWSER_VIEWPORT_WIDTH': '1920',
            'BROWSER_VIEWPORT_HEIGHT': '1080'
        }, clear=True):
            settings = Settings()
            assert settings.BROWSER_VIEWPORT_WIDTH == 1920
            assert settings.BROWSER_VIEWPORT_HEIGHT == 1080
    
    def test_timeout_configuration(self):
        with patch.dict(os.environ, {
            'BROWSER_TIMEOUT': '45',
            'BROWSER_NAVIGATION_TIMEOUT': '60',
            'BROWSER_MAX_RETRIES': '5'
        }, clear=True):
            settings = Settings()
            assert settings.BROWSER_TIMEOUT == 45
            assert settings.BROWSER_NAVIGATION_TIMEOUT == 60
            assert settings.BROWSER_MAX_RETRIES == 5

    def test_pool_configuration(self):
        with patch.dict(os.environ, {
            'MAX_BROWSER_INSTANCES': '10',
            'BROWSER_POOL_SIZE': '5'
        }, clear=True):
            settings = Settings()
            assert settings.MAX_BROWSER_INSTANCES == 10
            assert settings.BROWSER_POOL_SIZE == 5

    def test_debug_configuration(self):
        with patch.dict(os.environ, {
            'BROWSER_DEBUG': 'true',
            'BROWSER_SLOW_MO': '100'
        }, clear=True):
            settings = Settings()
            assert settings.BROWSER_DEBUG is True
            assert settings.BROWSER_SLOW_MO == 100

class TestConfigurationValidation:
    """Test configuration validation utilities."""
    
    def test_validate_required_settings(self):
        with patch.dict(os.environ, {
            'APP_NAME': 'Test App',
            'DEBUG': 'false'
        }, clear=True):
            settings = Settings()
            assert settings.app_name == 'Test App'
            assert settings.debug is False
            assert settings.host == '0.0.0.0'
            assert settings.port == 8000
    
    # --- THIS IS THE CORRECTED TEST ---
    def test_cors_origins_parsing(self):
        """Test CORS origins configuration parsing."""
        # For pydantic-settings, a list from an env var should be a JSON string
        env = {'CORS_ORIGINS': '["http://localhost:3000", "http://127.0.0.1:3000"]'}
        
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert isinstance(settings.cors_origins, list)
            assert len(settings.cors_origins) == 2
            assert 'http://localhost:3000' in settings.cors_origins
            assert 'http://127.0.0.1:3000' in settings.cors_origins
    
    def test_boolean_parsing(self):
        test_cases = [
            ('true', True), ('False', False), ('1', True), ('0', False)
        ]
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'BROWSER_HEADLESS': env_value}, clear=True):
                settings = Settings()
                assert settings.BROWSER_HEADLESS == expected

    def test_integer_parsing(self):
        with patch.dict(os.environ, {
            'PORT': '3000',
            'BROWSER_TIMEOUT': '45',
            'MAX_BROWSER_INSTANCES': '8'
        }, clear=True):
            settings = Settings()
            assert settings.port == 3000
            assert settings.BROWSER_TIMEOUT == 45
            assert settings.MAX_BROWSER_INSTANCES == 8
    
    def test_invalid_configuration_handling(self):
        with pytest.raises(Exception):
            with patch.dict(os.environ, {
                'PORT': 'invalid',
                'BROWSER_HEADLESS': 'maybe'
            }, clear=True):
                Settings()