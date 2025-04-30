import sys
import subprocess
import os
import matplotlib

def check_and_install_dependencies():
    """
    Check and install dependencies from requirements.txt
    """
    print("Checking and installing dependencies...")
    requirements_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    
    if not os.path.exists(requirements_path):
        print(f"Error: Requirements file not found at {requirements_path}")
        return False
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
        print("All dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False

def create_assets_directory():
    """
    Create assets directory for charts
    """
    print("Creating assets directory for charts...")
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "charts")
    
    try:
        os.makedirs(assets_dir, exist_ok=True)
        print(f"Assets directory created at {assets_dir}")
        return True
    except Exception as e:
        print(f"Error creating assets directory: {e}")
        return False

def check_matplotlib_backend():
    """
    Check and set matplotlib backend for non-interactive use
    """
    try:
        matplotlib.use('Agg')
        print("Matplotlib backend set to Agg for non-interactive use")
        return True
    except ImportError:
        print("Matplotlib not installed. Please run setup again after installing dependencies.")
        return False

def setup():
    """
    Main setup function
    """
    print("Starting analytics dashboard setup...")
    
    # Check and install dependencies
    if not check_and_install_dependencies():
        return False
    
    # Create assets directory
    if not create_assets_directory():
        return False
    
    # Check matplotlib backend
    if not check_matplotlib_backend():
        return False
    
    print("Setup completed successfully")
    return True

if __name__ == "__main__":
    success = setup()
    if success:
        print("Analytics dashboard setup completed successfully")
        sys.exit(0)
    else:
        print("Analytics dashboard setup failed")
        sys.exit(1) 