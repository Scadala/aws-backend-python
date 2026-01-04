import logging

# Set up logging
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    """Lambda function to handle logout
    
    Clears all session cookies and redirects to the home page.

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format (v2)

    context: object, required
        Lambda Context runtime methods and attributes

    Returns
    ------
    API Gateway Lambda Proxy Output Format (v2): dict
        Returns a 302 redirect to root path with expired cookies
    """
    logger.info("Logout initiated", extra={"event": event})
    
    # Get existing cookies to clear them
    cookies_to_clear = []
    existing_cookies = event.get('cookies') or []
    
    # Clear all session cookies by setting Max-Age=0
    for cookie in existing_cookies:
        if '=' in cookie:
            cookie_name = cookie.split('=')[0]
            # Clear the cookie by setting it to empty with Max-Age=0
            cookies_to_clear.append(f"{cookie_name}=; Max-Age=0; Path=/")
    
    logger.info(f"Clearing {len(cookies_to_clear)} cookies")
    
    return {
        "statusCode": 302,
        "headers": {
            "Location": "/"
        },
        "cookies": cookies_to_clear
    }
