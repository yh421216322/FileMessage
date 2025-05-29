"""
Implements a basic authenticated file server using Python's http.server.
"""
import http.server
import socketserver
import threading
import json
import os
import functools
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class AuthenticatedHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    A custom HTTP request handler that serves files from a specific directory
    and requires PIN-based authentication for access.
    """
    def __init__(self, *args, directory=None, current_full_pin_hash=None, **kwargs):
        if directory is None:
            raise ValueError("Shared directory must be provided.")
        if current_full_pin_hash is None:
            # This will be updated by the FileServer, but needs an initial value
            self.current_full_pin_hash = "" 
        else:
            self.current_full_pin_hash = current_full_pin_hash
        
        # Store the absolute path of the shared directory
        self.shared_directory_path = Path(directory).resolve()
        super().__init__(*args, directory=str(self.shared_directory_path), **kwargs)


    def _is_authenticated(self) -> bool:
        """Checks if the client is authenticated via the X-PIN-Hash header."""
        # The actual current_full_pin_hash is accessed via self.server.current_full_pin_hash
        # as the FileServer instance updates it there.
        client_pin_hash = self.headers.get('X-PIN-Hash')
        if client_pin_hash == self.server.current_full_pin_hash:
            return True
        return False

    def send_error_response(self, code, message=None):
        """Sends an error response and logs it."""
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if message:
            self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
        logger.warning(f"Sent error response {code} to {self.client_address[0]}: {message}")


    def translate_path(self, path: str) -> str:
        """
        Translates a path to the local filename system, ensuring it's within
        the shared directory.
        """
        # Call the superclass method, which uses its 'directory' (our shared_directory_path)
        translated_path = super().translate_path(path) 
        
        # Ensure the path is still within the shared directory after translation
        # (super().translate_path already does some of this with os.path.abspath)
        # but an extra check against our resolved shared_directory_path is good.
        abs_translated_path = Path(translated_path).resolve()
        
        if not str(abs_translated_path).startswith(str(self.shared_directory_path)):
            # This case should ideally not be reached if SimpleHTTPRequestHandler's
            # own directory serving logic is sound, but it's a safeguard.
            logger.warning(f"Path traversal attempt or invalid path: '{path}' translated to '{translated_path}' from client {self.client_address[0]}. Denying access.")
            return None # Indicate an invalid path

        return translated_path

    def do_GET(self):
        """Handles GET requests with PIN authentication and custom directory listing."""
        client_ip = self.client_address[0]
        logger.debug(f"GET request from {client_ip} for path: {self.path}")
        if not self._is_authenticated():
            logger.warning(f"Failed PIN authentication for GET request from {client_ip} for path {self.path}. PIN hash: {self.headers.get('X-PIN-Hash')}")
            self.send_error_response(403, "Forbidden: Invalid or missing PIN hash.")
            return
        
        logger.debug(f"Successful PIN authentication for GET request from {client_ip} for path {self.path}.")

        # translated_path will use self.directory set in __init__
        fpath = self.translate_path(self.path)
        if fpath is None: # Path traversal or other issue
            self.send_error_response(404, "File not found or invalid path.")
            return

        if os.path.isdir(fpath):
            try:
                logger.info(f"Serving directory listing for {fpath} to {client_ip}.")
                dir_contents = os.listdir(fpath)
                files = []
                subdirectories = []
                for item in dir_contents:
                    item_path = os.path.join(fpath, item)
                    if os.path.isdir(item_path):
                        subdirectories.append(item + "/")
                    else:
                        files.append(item)
                
                # Sort for consistent ordering
                files.sort()
                subdirectories.sort()

                response_data = {
                    "path": self.path, # Use the requested path, not the translated one
                    "files": files,
                    "directories": subdirectories
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                logger.debug(f"Successfully sent directory listing for {fpath} to {client_ip}.")
            except OSError as e:
                logger.error(f"Error listing directory {fpath} for {client_ip}: {e}", exc_info=True)
                self.send_error_response(500, f"Error listing directory: {e.strerror}")
        else:
            try:
                logger.info(f"Attempting to serve file {fpath} to {client_ip}.")
                super().do_GET() # This will send the file
                # SimpleHTTPRequestHandler doesn't provide easy hooks to know if send_head was successful
                # We assume if no exception, it was likely successful.
                # Actual success/failure is hard to determine without more complex subclassing.
                logger.debug(f"File {fpath} served or HEAD response sent to {client_ip}.")
            except ConnectionAbortedError:
                 logger.warning(f"Connection aborted by client {client_ip} while serving file {fpath}.")
            except ConnectionResetError:
                 logger.warning(f"Connection reset by client {client_ip} while serving file {fpath}.")
            except socket.error as e:
                logger.error(f"Socket error serving file {fpath} to {client_ip}: {e}", exc_info=True)
                # Cannot send error response if headers already sent or socket broken
            except Exception as e:
                logger.error(f"Unexpected error serving file {fpath} to {client_ip}: {e}", exc_info=True)
                # Cannot send error response if headers already sent


    def do_HEAD(self):
        """Handles HEAD requests with PIN authentication."""
        client_ip = self.client_address[0]
        logger.debug(f"HEAD request from {client_ip} for path: {self.path}")
        if not self._is_authenticated():
            logger.warning(f"Failed PIN authentication for HEAD request from {client_ip} for path {self.path}.")
            self.send_error_response(403, "Forbidden: Invalid or missing PIN hash.")
            return
        logger.debug(f"Successful PIN authentication for HEAD request from {client_ip} for path {self.path}.")
        super().do_HEAD()
    
    # Disable default HTML directory listing - our do_GET handles JSON for directories
    # Setting list_directory = False isn't directly available as a simple flag.
    # Our custom do_GET for directories effectively bypasses it.
    # We don't call super().list_directory() or similar.


class FileServer:
    """
    A threaded HTTP server to share files from a specific directory,
    requiring PIN-based authentication.
    """
    def __init__(self, host: str, port: int, shared_directory: str, current_full_pin_hash: str):
        """
        Initializes the FileServer.

        Args:
            host: The hostname or IP address to bind to.
            port: The port number to bind to.
            shared_directory: The absolute path to the directory to share.
            current_full_pin_hash: The current full SHA256 hash of the PIN.
        """
        self.host = host
        self.port = port
        
        # Ensure shared_directory is an absolute path and exists
        self.shared_directory = Path(shared_directory).resolve()
        if not self.shared_directory.is_dir():
            # Create the directory if it doesn't exist, or raise an error
            # For now, let's assume it should exist or be creatable by user action beforehand.
            # If auto-creation is needed, it can be added here.
            # os.makedirs(self.shared_directory, exist_ok=True)
            raise FileNotFoundError(f"Shared directory '{self.shared_directory}' not found or not a directory.")

        # This will be accessed by the handler via self.server.current_full_pin_hash
        self.current_full_pin_hash = current_full_pin_hash 
        
        # The handler needs access to shared_directory and current_full_pin_hash.
        # We make current_full_pin_hash an attribute of the HTTPServer instance itself.
        # The shared_directory is passed directly to the handler during its construction.
        handler_partial = functools.partial(
            AuthenticatedHTTPRequestHandler,
            directory=str(self.shared_directory)
            # current_full_pin_hash is not passed here, handler will get it from server instance
        )

        # We use ThreadingHTTPServer for easier thread management.
        # We need to make current_full_pin_hash accessible to the handler.
        # The handler can access its server instance via `self.server`.
        # So, we set current_full_pin_hash as an attribute on the server instance.
        class CustomTCPServer(socketserver.ThreadingTCPServer):
            # Allow address reuse
            allow_reuse_address = True
            # This attribute will be accessible by the handler as self.server.current_full_pin_hash
            current_full_pin_hash = current_full_pin_hash 
            # shared_directory is passed to handler directly, but could also be stored here if needed

        self.httpd = CustomTCPServer((self.host, self.port), handler_partial)
        self.server_thread = None
        logger.info(f"FileServer initialized to serve from '{self.shared_directory}' on {self.host}:{self.port}")

    def start(self):
        """Starts the HTTP server in a separate thread."""
        if self.server_thread and self.server_thread.is_alive():
            logger.warning("FileServer start called but server is already running.")
            return

        # The actual serve_forever loop is within httpd.
        # We wrap the call to serve_forever in our own try-except for thread-level errors,
        # though most errors related to request handling are within the handler.
        def _server_thread_runner():
            try:
                logger.info(f"FileServer thread starting, serving on {self.host}:{self.port}...")
                self.httpd.serve_forever()
                logger.info(f"FileServer thread on {self.host}:{self.port} finished serve_forever normally (likely due to shutdown()).")
            except KeyboardInterrupt: # Should be handled by main app usually
                logger.info(f"FileServer thread on {self.host}:{self.port} received KeyboardInterrupt.")
            except Exception as e:
                logger.critical(f"FileServer thread on {self.host}:{self.port} crashed: {e}", exc_info=True)
            finally:
                logger.info(f"FileServer thread on {self.host}:{self.port} exiting.")

        self.server_thread = threading.Thread(target=_server_thread_runner, daemon=True)
        self.server_thread.start()
        logger.info(f"FileServer started successfully on {self.host}:{self.port}")


    def stop(self):
        """Stops the HTTP server."""
        if not self.server_thread or not self.server_thread.is_alive():
            logger.warning("FileServer stop called but server is not running or thread is missing.")
            # Ensure httpd is cleaned up if it exists, even if thread is gone
            if self.httpd:
                try:
                    self.httpd.server_close() # Close the server socket
                    logger.info("FileServer socket closed as a precaution during stop (thread was not active).")
                except Exception as e:
                    logger.error(f"Error closing server socket during precautionary stop: {e}", exc_info=True)
            return

        logger.info(f"Stopping FileServer on {self.host}:{self.port}...")
        try:
            self.httpd.shutdown()  # Signal serve_forever to stop
            self.httpd.server_close() # Close the server socket
            logger.debug(f"FileServer {self.host}:{self.port} shutdown() and server_close() called.")
        except Exception as e:
            logger.error(f"Error during FileServer httpd.shutdown() or server_close(): {e}", exc_info=True)
        
        self.server_thread.join(timeout=5) 
        if self.server_thread.is_alive():
            logger.warning(f"FileServer thread on {self.host}:{self.port} did not stop cleanly after 5s timeout.")
        else:
            logger.info(f"FileServer on {self.host}:{self.port} stopped successfully.")
        self.server_thread = None


    def update_pin_hash(self, new_pin_hash: str):
        """
        Updates the PIN hash used for authentication.
        This is crucial for dynamic PIN changes.
        """
        self.httpd.current_full_pin_hash = new_pin_hash 
        logger.info(f"FileServer PIN hash updated for server on {self.host}:{self.port}.")


# Example Usage (for testing purposes)
if __name__ == '__main__':
    TEST_HOST = "localhost"
    TEST_PORT = 8080
    # Create a dummy shared directory for testing
    DUMMY_SHARED_DIR = Path("dummy_shared_files")
    DUMMY_SHARED_DIR.mkdir(exist_ok=True)
    (DUMMY_SHARED_DIR / "test_file1.txt").write_text("This is test file 1.")
    (DUMMY_SHARED_DIR / "test_file2.txt").write_text("This is test file 2.")
    (DUMMY_SHARED_DIR / "subdir").mkdir(exist_ok=True)
    (DUMMY_SHARED_DIR / "subdir" / "nested_file.txt").write_text("Nested content.")

    INITIAL_PIN = "1234"
    # Simulate hashing 
    import hashlib
    current_hashed_pin = hashlib.sha256(INITIAL_PIN.encode('utf-8')).hexdigest()
    
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    logger.info(f"Serving files from: {DUMMY_SHARED_DIR.resolve()}")
    logger.info(f"Initial PIN hash for server: {current_hashed_pin}")
    logger.info(f"Access with header: X-PIN-Hash: {current_hashed_pin}")

    file_server = FileServer(
        host=TEST_HOST,
        port=TEST_PORT,
        shared_directory=str(DUMMY_SHARED_DIR),
        current_full_pin_hash=current_hashed_pin
    )
    file_server.start()

    logger.info(f"HTTP server running on http://{TEST_HOST}:{TEST_PORT}")
    logger.info("Try accessing files with a tool like curl or Postman.")
    logger.info("Example: curl -H \"X-PIN-Hash: <hash>\" http://localhost:8080/test_file1.txt")
    
    try:
        # Keep the main thread alive to allow the server thread to run
        while file_server.server_thread and file_server.server_thread.is_alive():
            time.sleep(1)
            # Simulate PIN change (for testing update_pin_hash)
            # if int(time.time()) % 30 == 0:
            #     new_pin_example = str(random.randint(1000,9999))
            #     new_hashed_pin_example = hashlib.sha256(new_pin_example.encode('utf-8')).hexdigest()
            #     file_server.update_pin_hash(new_hashed_pin_example)
            #     logger.info(f"Test PIN hash updated to: {new_hashed_pin_example} (for PIN {new_pin_example})")

    except KeyboardInterrupt:
        logger.info("\nKeyboardInterrupt received, shutting down server...")
    except Exception as e:
        logger.critical(f"Unhandled exception in example main: {e}", exc_info=True)
    finally:
        file_server.stop()
        # Clean up dummy directory (optional for testing)
        # import shutil
        # shutil.rmtree(DUMMY_SHARED_DIR)
        logger.info("Server shutdown complete.")
