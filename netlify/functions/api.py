import sys
from pathlib import Path

# Add the parent folder of 'app' to the Python system path 
# so Netlify Functions can correctly find and import our modules.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.main import app
from mangum import Mangum

# This handler will receive the AWS API Gateway events sent by Netlify
handler = Mangum(app, api_gateway_base_path="/.netlify/functions/api")
