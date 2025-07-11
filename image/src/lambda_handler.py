from mangum import Mangum
from app.main import app

# Create the Lambda handler
handler = Mangum(app, lifespan="off")

# For backwards compatibility, also export as lambda_handler
lambda_handler = handler