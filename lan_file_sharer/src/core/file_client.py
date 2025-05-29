"""
Implements a client to interact with the FileServer for listing and downloading files.
"""
import requests
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FileClient:
    """
    A client for interacting with a remote FileServer instance.
    Allows listing remote directories and downloading files with PIN authentication.
    """

    def __init__(self, current_full_pin_hash: str):
        """
        Initializes the FileClient.

        Args:
            current_full_pin_hash: The current full SHA256 hash of the PIN
                                   to be used for authentication.
        """
        self.current_full_pin_hash = current_full_pin_hash
        self.session = requests.Session() # Use a session for potential connection pooling

    def update_pin_hash(self, new_pin_hash: str):
        """
        Updates the PIN hash used for authentication.

        Args:
            new_pin_hash: The new full SHA256 hash of the PIN.
        """
        self.current_full_pin_hash = new_pin_hash
        logger.debug(f"FileClient PIN hash updated.")

    def _prepare_headers(self) -> dict:
        """Prepares the authentication headers."""
        return {'X-PIN-Hash': self.current_full_pin_hash}

    def list_files(self, peer_address: str, remote_path: str = "/") -> dict:
        """
        Lists files and directories at a given path on a remote peer's FileServer.

        Args:
            peer_address: The address of the target peer's server (e.g., "ip:port" or "hostname:port").
            remote_path: The path on the remote server to list (defaults to root "/").
                         Should start with '/'.

        Returns:
            A dictionary containing the listing (e.g., {"files": [], "directories": [], "path": "/"})
            if successful.
            Returns a dictionary with an "error" key (e.g., {"error": "message"}) on failure.
        """
        if not remote_path.startswith("/"):
            remote_path = "/" + remote_path
        
        # Ensure peer_address doesn't have a scheme already, then prepend http://
        if "://" in peer_address:
            base_url = peer_address
        else:
            base_url = f"http://{peer_address}"

        # Ensure remote_path is correctly joined, avoiding double slashes if base_url ends with /
        # and remote_path starts with /
        url = f"{base_url.rstrip('/')}{remote_path}"
        
        headers = self._prepare_headers()

        try:
            logger.info(f"Listing files from {url} with PIN hash prefix {self.current_full_pin_hash[:8]}...")
            response = self.session.get(url, headers=headers, timeout=10) 
            response.raise_for_status()  

            if response.headers.get('Content-Type') == 'application/json':
                logger.debug(f"Successfully listed files from {url}. Response: {response.json()}")
                return response.json()
            else:
                error_msg = f"Unexpected content type from {url}: {response.headers.get('Content-Type')}"
                logger.error(error_msg)
                return {"error": error_msg}

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e.response.status_code} for URL {url}."
            try:
                error_details = e.response.json()
                error_msg += f" Server message: {error_details.get('error', e.response.text)}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg, "status_code": e.response.status_code}
            except json.JSONDecodeError:
                error_msg += f" Raw response: {e.response.text}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg, "status_code": e.response.status_code}
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection Error: Could not connect to {url}. Details: {e}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except requests.exceptions.Timeout:
            error_msg = f"Timeout: The request to {url} timed out."
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except requests.exceptions.RequestException as e: 
            error_msg = f"Request Error for {url}: An unexpected error occurred. Details: {e}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except json.JSONDecodeError as e: # Should be caught by HTTPError parsing, but as a fallback
            error_msg = f"JSON Decode Error: Invalid JSON response from server {url}. Details: {e}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}


    def download_file(self, peer_address: str, remote_file_path: str, local_save_path: str, progress_callback=None) -> bool:
        """
        Downloads a file from a remote peer's FileServer.

        Args:
            peer_address: The address of the target peer's server (e.g., "ip:port").
            remote_file_path: The full path to the file on the remote server (e.g., "/folder/file.txt").
            local_save_path: The local path (including filename) where the downloaded file should be saved.
            progress_callback: An optional function that takes (current_bytes, total_bytes)
                               to report download progress.

        Returns:
            True if the download was successful, False otherwise.
        """
        if not remote_file_path.startswith("/"):
            remote_file_path = "/" + remote_file_path

        if "://" in peer_address:
            base_url = peer_address
        else:
            base_url = f"http://{peer_address}"
        
        url = f"{base_url.rstrip('/')}{remote_file_path}"
        headers = self._prepare_headers()

        try:
            logger.info(f"Attempting to download '{remote_file_path}' from {peer_address} to '{local_save_path}'")
            # Ensure the local directory exists
            Path(local_save_path).parent.mkdir(parents=True, exist_ok=True)

            with self.session.get(url, headers=headers, stream=True, timeout=15) as response: 
                response.raise_for_status()

                total_bytes = int(response.headers.get('content-length', 0))
                logger.debug(f"Starting download of {total_bytes} bytes from {url} to {local_save_path}.")
                current_bytes = 0

                with open(local_save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192): # 8KB chunks
                        if chunk: # filter out keep-alive new chunks
                            f.write(chunk)
                            current_bytes += len(chunk)
                            if progress_callback:
                                progress_callback(current_bytes, total_bytes)
                
                if progress_callback and current_bytes < total_bytes and total_bytes > 0 : # Ensure callback is called one last time
                    progress_callback(current_bytes, total_bytes if total_bytes > 0 else current_bytes)
                
                logger.info(f"Successfully downloaded {current_bytes} bytes from {url} to {local_save_path}")
                return True

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error during download from {url}: {e.response.status_code} - {e.response.text}", exc_info=True)
            if os.path.exists(local_save_path): os.remove(local_save_path)
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error during download from {url}: {e}", exc_info=True)
            return False
        except requests.exceptions.Timeout:
            logger.error(f"Timeout during download from {url}", exc_info=True)
            if os.path.exists(local_save_path): os.remove(local_save_path)
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error during download from {url}: {e}", exc_info=True)
            if os.path.exists(local_save_path): os.remove(local_save_path)
            return False
        except IOError as e:
            logger.error(f"File IO Error: Could not write to {local_save_path}. Details: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.critical(f"Unexpected error during download from {url} to {local_save_path}: {e}", exc_info=True)
            if os.path.exists(local_save_path): os.remove(local_save_path)
            return False


# Example Usage (for testing purposes - requires a running FileServer)
if __name__ == '__main__':
    # This example assumes a FileServer is running locally on port 8080, etc.
    # For this example to run, you might need to run file_server.py separately.
    
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    import hashlib # For example PIN hashing
    TEST_PIN = "1234" 
    hashed_pin_for_client = hashlib.sha256(TEST_PIN.encode('utf-8')).hexdigest()

    client = FileClient(current_full_pin_hash=hashed_pin_for_client)
    SERVER_ADDRESS = "localhost:8080" 

    logger.info(f"--- Test: Listing root directory from {SERVER_ADDRESS}/ ---")
    listing_result = client.list_files(SERVER_ADDRESS, "/")
    if "error" in listing_result:
        logger.error(f"Error listing files: {listing_result['error']}")
    else:
        logger.info(f"Successfully listed files at '/': {json.dumps(listing_result, indent=2)}")

    logger.info(f"--- Test: Listing /subdir/ from {SERVER_ADDRESS}/ ---")
    listing_subdir_result = client.list_files(SERVER_ADDRESS, "/subdir/")
    if "error" in listing_subdir_result:
        logger.error(f"Error listing files in /subdir/: {listing_subdir_result['error']}")
    else:
        logger.info(f"Successfully listed files at '/subdir/': {json.dumps(listing_subdir_result, indent=2)}")

    REMOTE_FILE = "/test_file1.txt"
    LOCAL_DESTINATION = "downloaded_test_file1.txt"
    logger.info(f"--- Test: Downloading {REMOTE_FILE} to {LOCAL_DESTINATION} ---")

    def my_progress_callback(current, total):
        if total > 0:
            logger.info(f"Download progress: {current}/{total} bytes ({current*100/total:.2f}%)")
        else:
            logger.info(f"Download progress: {current} bytes (total size unknown)")

    if client.download_file(SERVER_ADDRESS, REMOTE_FILE, LOCAL_DESTINATION, progress_callback=my_progress_callback):
        logger.info(f"Successfully downloaded {REMOTE_FILE} to {LOCAL_DESTINATION}")
        # Optional: os.remove(LOCAL_DESTINATION) 
    else:
        logger.error(f"Failed to download {REMOTE_FILE}")

    logger.info(f"--- Test: Invalid PIN ---")
    client.update_pin_hash("invalid_pin_hash")
    invalid_listing = client.list_files(SERVER_ADDRESS, "/")
    if "error" in invalid_listing and invalid_listing.get("status_code") == 403:
        logger.info(f"Correctly failed with invalid PIN: {invalid_listing['error']}")
    else:
        logger.error(f"Test failed: Did not get expected 403 error for invalid PIN. Got: {invalid_listing}")
    
    logger.info(f"--- Test: Non-existent file download ---")
    client.update_pin_hash(hashed_pin_for_client) # Reset to valid PIN
    if not client.download_file(SERVER_ADDRESS, "/non_existent_file.txt", "ne_download.txt"):
        logger.info("Correctly failed to download non-existent file.")
    else:
        logger.error("Test failed: Incorrectly succeeded in downloading non-existent file.")
        # Optional: os.remove("ne_download.txt")

    logger.info("--- FileClient example usage finished. ---")
