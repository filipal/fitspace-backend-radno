"""
Pytest configuration file
"""
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging for tests
import logging
logging.basicConfig(level=logging.INFO)
