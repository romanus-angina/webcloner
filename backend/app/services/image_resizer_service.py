import os
import logging
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageOps
import tempfile

from ..utils.logger import get_logger

logger = get_logger(__name__)

class ImageResizerService:
    """
    Service to resize images to comply with Claude's API limits.
    Claude's vision API has a maximum dimension limit of 8000 pixels.
    """
    
    def __init__(self):
        self.max_dimension = 7500  # Leave some buffer below 8000px limit
        self.quality = 85  # JPEG quality for compressed images
        
    def resize_image_for_claude(self, image_path: str) -> str:
        """
        Resize an image if it exceeds Claude's dimension limits.
        
        Args:
            image_path: Path to the original image
            
        Returns:
            Path to the resized image (might be the same as input if no resize needed)
            
        Raises:
            Exception: If image processing fails
        """
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            # Open and check image dimensions
            with Image.open(image_path) as img:
                original_width, original_height = img.size
                max_original_dimension = max(original_width, original_height)
                
                logger.info(f"Image dimensions: {original_width}x{original_height}")
                
                # If image is within limits, return original path
                if max_original_dimension <= self.max_dimension:
                    logger.info("Image is within Claude's dimension limits")
                    return image_path
                
                # Calculate new dimensions while maintaining aspect ratio
                scale_factor = self.max_dimension / max_original_dimension
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                logger.info(f"Resizing image from {original_width}x{original_height} to {new_width}x{new_height}")
                
                # Create resized image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Generate output path
                original_path = Path(image_path)
                output_path = original_path.parent / f"{original_path.stem}_resized{original_path.suffix}"
                
                # Save resized image
                if original_path.suffix.lower() in ['.jpg', '.jpeg']:
                    resized_img.save(str(output_path), 'JPEG', quality=self.quality, optimize=True)
                else:
                    resized_img.save(str(output_path), optimize=True)
                
                logger.info(f"Resized image saved to: {output_path}")
                return str(output_path)
                
        except Exception as e:
            logger.error(f"Failed to resize image {image_path}: {str(e)}")
            raise
    
    def get_image_dimensions(self, image_path: str) -> Tuple[int, int]:
        """
        Get the dimensions of an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (width, height)
        """
        try:
            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            logger.error(f"Failed to get image dimensions for {image_path}: {str(e)}")
            raise
    
    def is_image_too_large(self, image_path: str) -> bool:
        """
        Check if an image exceeds Claude's dimension limits.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            True if image is too large for Claude's API
        """
        try:
            width, height = self.get_image_dimensions(image_path)
            return max(width, height) > self.max_dimension
        except Exception:
            return False  # If we can't read the image, assume it's not too large
    
    def cleanup_resized_image(self, image_path: str) -> None:
        """
        Clean up a resized image file if it was created by this service.
        
        Args:
            image_path: Path to the potentially resized image
        """
        try:
            if "_resized" in str(image_path) and os.path.exists(image_path):
                os.remove(image_path)
                logger.debug(f"Cleaned up resized image: {image_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup resized image {image_path}: {str(e)}")

# Global instance
image_resizer_service = ImageResizerService()