import os
import sys
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Optional


def setup_logging():
    """Set up logging for the setup script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)


def run_command(command: str, description: str, logger: logging.Logger) -> Optional[str]:
    """
    Run a shell command and handle errors.
    
    Args:
        command: Shell command to run
        description: Human-readable description of the command
        logger: Logger instance
        
    Returns:
        Command output if successful, None if failed
    """
    logger.info(f"Starting: {description}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
        )
        logger.info(f"Completed: {description}")
        return result.stdout
        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout: {description} took too long")
        return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed: {description}")
        logger.error(f"Error code: {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        return None
        
    except Exception as e:
        logger.error(f"Unexpected error in {description}: {str(e)}")
        return None


def check_prerequisites(logger: logging.Logger) -> bool:
    """
    Check if required tools are installed.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if all prerequisites are met, False otherwise
    """
    logger.info("Checking prerequisites")
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error(f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        return False
    logger.info(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check if uv is installed
    if shutil.which("uv") is None:
        logger.error("uv package manager not found")
        logger.info("Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False
    logger.info("uv package manager available")
    
    # Check if git is available (optional but recommended)
    if shutil.which("git") is None:
        logger.warning("git not found - version control will not be available")
    else:
        logger.info("git available")
    
    return True


def create_directories(logger: logging.Logger) -> bool:
    """
    Create necessary project directories.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Creating project directories")
    
    directories = [
        "data",
        "data/screenshots", 
        "data/generated",
        "data/assets",
        "app/api/middleware",
        "logs",
        "tests",
        "docs"
    ]
    
    try:
        for directory in directories:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")
        
        logger.info("All directories created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create directories: {str(e)}")
        return False


def setup_environment(logger: logging.Logger) -> bool:
    """
    Set up environment configuration.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Setting up environment configuration")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    try:
        if not env_file.exists():
            if env_example.exists():
                shutil.copy(env_example, env_file)
                logger.info("Created .env from .env.example")
            else:
                # Create basic .env file
                with open(env_file, "w") as f:
                    f.write("""# Orchids Website Cloner Environment Configuration
DEBUG=true
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8000

# API Keys (replace with actual values)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60

# File Storage
TEMP_STORAGE_PATH=./data
MAX_FILE_SIZE=10485760

# Logging
LOG_LEVEL=INFO
""")
                logger.info("Created basic .env file")
            
            logger.warning("Please edit .env and add your actual API keys")
        else:
            logger.info(".env file already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to set up environment: {str(e)}")
        return False


def install_dependencies(logger: logging.Logger) -> bool:
    """
    Install Python dependencies using uv.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Installing Python dependencies")
    
    # Check if pyproject.toml exists
    if not Path("pyproject.toml").exists():
        logger.error("pyproject.toml not found")
        return False
    
    # Install dependencies
    if run_command("uv sync", "Installing Python dependencies", logger):
        logger.info("Python dependencies installed successfully")
        return True
    else:
        logger.error("Failed to install Python dependencies")
        logger.info("You can try manually running: uv sync")
        return False


def install_playwright(logger: logging.Logger) -> bool:
    """
    Install Playwright browsers.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Installing Playwright browsers")
    
    if run_command("uv run playwright install", "Installing Playwright browsers", logger):
        logger.info("Playwright browsers installed successfully")
        return True
    else:
        logger.error("Failed to install Playwright browsers")
        logger.info("You can try manually running: uv run playwright install")
        return False


def test_installation(logger: logging.Logger) -> bool:
    """
    Test the installation by importing the FastAPI app.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if test passes, False otherwise
    """
    logger.info("Testing installation")
    
    test_command = (
        "uv run python -c "
        "\"from app.main import app; "
        "from app.config import settings; "
        "print('FastAPI app loads successfully')\""
    )
    
    if run_command(test_command, "Testing FastAPI app import", logger):
        logger.info("Installation test passed")
        return True
    else:
        logger.error("Installation test failed")
        logger.error("The FastAPI application cannot be imported")
        return False


def create_gitignore(logger: logging.Logger) -> bool:
    """
    Create .gitignore file if it doesn't exist.
    
    Args:
        logger: Logger instance
        
    Returns:
        True if successful, False otherwise
    """
    gitignore_path = Path(".gitignore")
    
    if gitignore_path.exists():
        logger.info(".gitignore already exists")
        return True
    
    try:
        with open(gitignore_path, "w") as f:
            f.write("""# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# Environment Variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
logs/
*.log

# Data directories
data/screenshots/
data/generated/
data/assets/

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# FastAPI
.pytest_cache

# Temporary files
tmp/
temp/
""")
        logger.info("Created .gitignore file")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create .gitignore: {str(e)}")
        return False


def print_next_steps(logger: logging.Logger, success: bool):
    """
    Print next steps for the user.
    
    Args:
        logger: Logger instance
        success: Whether setup was successful
    """
    if success:
        logger.info("Setup completed successfully!")
        print("\n" + "="*60)
        print("SETUP COMPLETE - Next Steps:")
        print("="*60)
        print("\n1. Configure API Keys:")
        print("   Edit .env file and replace placeholder values:")
        print("   - ANTHROPIC_API_KEY=your_actual_anthropic_key")
        
        print("\n2. Start Development Server:")
        print("   uv run fastapi dev")
        print("   # Server will start at http://localhost:8000")
        
        print("\n3. Test the API:")
        print("   # Health check")
        print("   curl http://localhost:8000/health")
        print("   # API documentation")
        print("   open http://localhost:8000/docs")
        
        print("\n4. Development Commands:")
        print("   uv run fastapi dev              # Start with auto-reload")
        print("   uv run python -m pytest        # Run tests (when added)")
        print("   uv add <package>                # Add new dependency")
        print("   uv run python app/main.py      # Alternative start method")
        
        print("\n5. Project Structure:")
        print("   app/                 # Main application code")
        print("   app/api/routes/      # API endpoint definitions")
        print("   app/models/          # Pydantic request/response models")
        print("   app/services/        # Business logic services")
        print("   app/utils/           # Utility functions and logging")
        print("   data/                # Temporary file storage")
        print("   logs/                # Application logs")
        
        print("\n6. Logging:")
        print("   Application logs are written to:")
        print("   - Console (colored output)")
        print("   - logs/website_cloner.log (all messages)")
        print("   - logs/website_cloner_errors.log (errors only)")
        
        print("\nFor more information, check the documentation in docs/")
        print("="*60)
        
    else:
        logger.error("Setup completed with errors")
        print("\n" + "="*60)
        print("SETUP INCOMPLETE - Please address the errors above")
        print("="*60)
        print("\nCommon solutions:")
        print("- Ensure Python 3.8+ is installed")
        print("- Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("- Check network connectivity for downloads")
        print("- Ensure you have write permissions in this directory")
        print("="*60)


def check_system_requirements(logger: logging.Logger) -> dict:
    """
    Check system requirements and return status.
    
    Args:
        logger: Logger instance
        
    Returns:
        Dictionary with system information
    """
    logger.info("Checking system requirements")
    
    system_info = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
        "uv_available": shutil.which("uv") is not None,
        "git_available": shutil.which("git") is not None,
        "current_directory": str(Path.cwd()),
        "write_permissions": os.access(".", os.W_OK)
    }
    
    logger.info(f"System information: {system_info}")
    return system_info


def main():
    """Main setup function."""
    # Set up logging
    logger = setup_logging()
    
    logger.info("Starting Orchids Website Cloner Backend Setup")
    logger.info("="*50)
    
    # Check system requirements
    system_info = check_system_requirements(logger)
    
    # Track setup success
    setup_steps = []
    
    # Run setup steps
    steps = [
        ("Prerequisites Check", lambda: check_prerequisites(logger)),
        ("Directory Creation", lambda: create_directories(logger)),
        ("Environment Setup", lambda: setup_environment(logger)),
        ("Dependency Installation", lambda: install_dependencies(logger)),
        ("Playwright Installation", lambda: install_playwright(logger)),
        ("GitIgnore Creation", lambda: create_gitignore(logger)),
        ("Installation Test", lambda: test_installation(logger))
    ]
    
    for step_name, step_func in steps:
        logger.info(f"Starting step: {step_name}")
        success = step_func()
        setup_steps.append((step_name, success))
        
        if success:
            logger.info(f"Completed step: {step_name}")
        else:
            logger.error(f"Failed step: {step_name}")
            # Continue with other steps even if one fails
    
    # Summary
    successful_steps = [name for name, success in setup_steps if success]
    failed_steps = [name for name, success in setup_steps if not success]
    
    logger.info(f"Setup summary: {len(successful_steps)}/{len(setup_steps)} steps completed")
    
    if failed_steps:
        logger.warning(f"Failed steps: {', '.join(failed_steps)}")
    
    # Print next steps
    overall_success = len(failed_steps) == 0
    print_next_steps(logger, overall_success)
    
    # Exit with appropriate code
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()