"""
Interactive authentication for local development.

This module provides browser-based authentication flow for Python scripts
running in local development environments.
"""

import logging
import os
import socket
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

import jwt

from kontext.common.constants import ApiEnvVars, AuthEnvVars, InteractiveAuthDefaults
from kontext.common.utils import poll_until

from .base_auth import AuthBase, AuthenticationError

logger = logging.getLogger(__name__)


class InteractiveAuthConfig:
    """Configuration for interactive authentication."""

    def __init__(
        self,
        api_base_url: str,
        callback_port: int = InteractiveAuthDefaults.CALLBACK_PORT,
        timeout_seconds: int = InteractiveAuthDefaults.TIMEOUT_SECONDS,
        auto_open_browser: bool = InteractiveAuthDefaults.AUTO_OPEN_BROWSER,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.callback_port = callback_port
        self.timeout_seconds = timeout_seconds
        self.auto_open_browser = auto_open_browser

    @classmethod
    def from_environment(cls) -> "InteractiveAuthConfig":
        """Create configuration from environment variables."""
        api_base_url = os.getenv(ApiEnvVars.API_URL, ApiEnvVars.DEFAULT_API_URL)
        return cls(
            api_base_url=api_base_url,
            callback_port=int(
                os.getenv(
                    AuthEnvVars.AUTH_CALLBACK_PORT,
                    str(InteractiveAuthDefaults.CALLBACK_PORT),
                )
            ),
            timeout_seconds=int(
                os.getenv(
                    AuthEnvVars.AUTH_TIMEOUT_SECONDS,
                    str(InteractiveAuthDefaults.TIMEOUT_SECONDS),
                )
            ),
            auto_open_browser=os.getenv(AuthEnvVars.AUTH_AUTO_OPEN_BROWSER, "true").lower()
            == "true",
        )


class AuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for authentication callback."""

    def __init__(self, auth_result_container: dict, *args, **kwargs):
        self.auth_result_container = auth_result_container
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET request for authentication callback."""
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            if parsed_url.path == "/auth/callback":
                # Extract tokens from query parameters
                access_token = query_params.get("access_token", [None])[0]
                refresh_token = query_params.get("refresh_token", [None])[0]
                expires_in = query_params.get("expires_in", [None])[0]
                error = query_params.get("error", [None])[0]

                if error:
                    self.auth_result_container["error"] = error
                    self._send_error_response(f"Authentication failed: {error}")
                elif access_token:
                    # Calculate expiration time
                    expires_at = None
                    if expires_in:
                        try:
                            expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
                        except ValueError:
                            logger.warning(f"Invalid expires_in value: {expires_in}")

                    self.auth_result_container["tokens"] = {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                    }
                    self._send_success_response()
                else:
                    self.auth_result_container["error"] = "No access token received"
                    self._send_error_response("Authentication failed: No access token received")
            else:
                self._send_not_found_response()

        except Exception as e:
            logger.error(f"Error handling auth callback: {e}")
            self.auth_result_container["error"] = str(e)
            self._send_error_response(f"Internal error: {e!s}")

    def _send_success_response(self):
        """Send success response to browser."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                }
                .success { color: #28a745; }
                .container { max-width: 500px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="success">Authentication Successful</h1>
                <p>You have been successfully authenticated with Kontext.</p>
                <p>You can now close this browser window and return to your application.
                </p>
            </div>
            <script>
                // Auto-close after 3 seconds
                setTimeout(() => {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """

        self._send_html_response(200, html_content)

    def _send_error_response(self, error_message: str):
        """Send error response to browser."""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                }}
                .error {{ color: #dc3545; }}
                .container {{ max-width: 500px; margin: 0 auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">Authentication Failed</h1>
                <p>{error_message}</p>
                <p>Please try again or check your configuration.</p>
            </div>
        </body>
        </html>
        """

        self._send_html_response(400, html_content)

    def _send_not_found_response(self):
        """Send 404 response."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Not Found</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    padding: 50px;
                }
                .container { max-width: 500px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>404 - Not Found</h1>
                <p>The requested page was not found.</p>
            </div>
        </body>
        </html>
        """

        self._send_html_response(404, html_content)

    def _send_html_response(self, status_code: int, html_content: str):
        """Send HTML response with given status code."""
        self.send_response(status_code)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(len(html_content.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


class InteractiveAuth(AuthBase):
    """Interactive authentication implementation for local development."""

    def __init__(self, config: InteractiveAuthConfig):
        super().__init__()  # Initialize base class
        self.config = config
        self._tokens: dict | None = None
        self._server: HTTPServer | None = None
        self._server_thread: Thread | None = None

    async def authenticate(self) -> bool:
        """Perform interactive authentication.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Check if we already have valid credentials
            if self._tokens and self.is_credentials_valid():
                return True

            # Start callback server
            callback_url = self._start_callback_server()

            # Open browser for authentication
            auth_url = self._build_auth_url(callback_url)

            if self.config.auto_open_browser:
                logger.info(f"Opening browser for authentication: {auth_url}")
                webbrowser.open(auth_url)
            else:
                logger.info("Please open the following URL in your browser to authenticate:")
                logger.info(auth_url)

            # Wait for authentication result
            tokens = await self._wait_for_authentication()
            self._tokens = tokens

            # Set credentials with expiration for base class
            expires_in = 3600  # Default 1 hour if not specified
            if tokens.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(tokens["expires_at"].replace("Z", "+00:00"))
                    expires_in = int((expires_at - datetime.now(UTC)).total_seconds())
                except (ValueError, TypeError):
                    pass

            self.set_credentials(tokens["access_token"], expires_in)

            return True

        except Exception as e:
            logger.error(f"Interactive authentication failed: {e}")
            raise AuthenticationError(f"Interactive authentication failed: {e!s}") from e
        finally:
            self._stop_callback_server()

    def get_user_id(self) -> str | None:
        """
        Extract user ID from the current access token

        Returns:
            User ID string if available, None otherwise
        """
        token = self.get_credentials()
        if not token and self._tokens:
            token = self._tokens.get("access_token")

        if not token:
            return None

        try:
            # Decode token without verification to extract claims
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload.get("sub")
        except Exception as e:
            self.logger.warning(f"Failed to extract user ID from token: {e}")
            return None

    async def refresh_if_needed(self) -> bool:
        """Refresh credentials if needed.

        Returns:
            True if credentials are valid/refreshed, False otherwise
        """
        if not self._tokens or not self.is_credentials_valid():
            # Re-authenticate if credentials are invalid
            return await self.authenticate()

        return True

    def _start_callback_server(self) -> str:
        """Start HTTP server for authentication callback."""
        self._auth_result = {}

        # Find available port
        port = self._find_available_port(self.config.callback_port)

        # Create handler with auth result container
        def handler_factory(*args, **kwargs):
            return AuthCallbackHandler(self._auth_result, *args, **kwargs)

        # Start server
        self._server = HTTPServer(("localhost", port), handler_factory)
        self._server_thread = Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

        callback_url = f"http://localhost:{port}/auth/callback"
        logger.info(f"Started authentication callback server on {callback_url}")

        return callback_url

    def _stop_callback_server(self):
        """Stop the callback server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

        if self._server_thread:
            self._server_thread.join(timeout=1)
            self._server_thread = None

    def _find_available_port(self, preferred_port: int) -> int:
        """Find an available port, starting with the preferred port."""
        for port in range(preferred_port, preferred_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("localhost", port))
                    return port
            except OSError:
                continue

        raise RuntimeError(f"Could not find available port starting from {preferred_port}")

    def _build_auth_url(self, callback_url: str) -> str:
        """Build authentication URL for browser."""
        # In a real implementation, this would redirect to the React app's login page
        # with the callback URL as a parameter
        app_url = os.getenv(ApiEnvVars.APP_URL, ApiEnvVars.DEFAULT_APP_URL)

        # The React app should handle this route and redirect to callback_url
        # after successful login
        return f"{app_url}/client-login?callback={callback_url}"

    async def _wait_for_authentication(self) -> dict:
        """Wait for authentication to complete."""
        timeout = self.config.timeout_seconds

        async def check_auth() -> dict | None:
            if "tokens" in self._auth_result:
                logger.info("Authentication successful")
                return self._auth_result["tokens"]
            elif "error" in self._auth_result:
                raise AuthenticationError(f"Authentication failed: {self._auth_result['error']}")
            return None

        result = await poll_until(check_auth, timeout_seconds=timeout, poll_interval_seconds=0.5)

        if result:
            return result

        raise AuthenticationError(f"Authentication timed out after {timeout} seconds")
