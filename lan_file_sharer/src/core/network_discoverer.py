"""
Handles network discovery for the LAN File Sharer application using UDP broadcasting.
"""
import socket
import threading
import json
import time
import uuid
import logging

logger = logging.getLogger(__name__)

# Network discovery constants
BROADCAST_PORT = 60000
BROADCAST_INTERVAL_SECONDS = 10
APP_ID = "LAN_FILE_SHARER_V1"


class DiscoveryBroadcaster:
    """
    Broadcasts presence to other peers on the network.
    """
    def __init__(self, peer_id: str, service_port: int, pin_hash_prefix: str):
        """
        Initializes the DiscoveryBroadcaster.

        Args:
            peer_id: A unique identifier for this application instance.
            service_port: The port number where this instance's file service will run.
            pin_hash_prefix: The first 8 characters of the hashed PIN.
        """
        self.peer_id = peer_id
        self.service_port = service_port
        self.pin_hash_prefix = pin_hash_prefix
        self.sock = None
        self.broadcasting_thread = None
        self._running = False

    def start(self):
        """
        Starts broadcasting presence in a separate thread.
        """
        if self._running:
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._running = True
        self.broadcasting_thread = threading.Thread(target=self._broadcast_presence, daemon=True)
        self.broadcasting_thread.start()
        logger.info(f"DiscoveryBroadcaster started for peer_id: {self.peer_id}")

    def _broadcast_presence(self):
        """
        Periodically broadcasts a JSON message with peer information.
        """
        try:
            message_data = {
                "app_id": APP_ID,
                "peer_id": self.peer_id,
                "service_port": self.service_port,
                "pin_hash_prefix": self.pin_hash_prefix
            }
            message = json.dumps(message_data).encode('utf-8')
            logger.debug(f"Broadcaster using message: {message_data}")

            while self._running:
                try:
                    self.sock.sendto(message, ('<broadcast>', BROADCAST_PORT))
                    logger.debug(f"Broadcasted presence: {message_data}")
                except socket.error as e:
                    logger.error(f"Error broadcasting: {e}", exc_info=True)
                    # Handle error, maybe stop broadcasting or retry later
                    if not self._running: # Check if stop() was called during sendto
                        logger.info("Broadcaster stopping due to _running being false after socket error.")
                        break
                time.sleep(BROADCAST_INTERVAL_SECONDS)
        except Exception as e:
            logger.critical(f"Unhandled exception in DiscoveryBroadcaster thread ({self.peer_id}): {e}", exc_info=True)
        finally:
            logger.info(f"DiscoveryBroadcaster thread ({self.peer_id}) finished.")


    def stop(self):
        """
        Stops the broadcasting thread and closes the socket.
        """
        logger.info(f"Stopping DiscoveryBroadcaster for peer_id: {self.peer_id}")
        self._running = False
        if self.broadcasting_thread and self.broadcasting_thread.is_alive():
            self.broadcasting_thread.join(timeout=1) 
        if self.sock:
            try:
                self.sock.close()
                logger.debug("Broadcaster socket closed.")
            except Exception as e:
                logger.error(f"Error closing broadcaster socket: {e}", exc_info=True)
            self.sock = None
        logger.info(f"DiscoveryBroadcaster stopped for peer_id: {self.peer_id}")


class DiscoveryListener:
    """
    Listens for broadcasts from other peers on the network.
    """
    def __init__(self, current_pin_hash_prefix: str, own_peer_id: str):
        """
        Initializes the DiscoveryListener.

        Args:
            current_pin_hash_prefix: The first 8 characters of the current instance's hashed PIN.
            own_peer_id: The peer_id of the current instance, to ignore self-broadcasts.
        """
        self.current_pin_hash_prefix = current_pin_hash_prefix
        self.own_peer_id = own_peer_id
        self.discovered_peers = {}  # Key: peer_id, Value: {"address": "ip:service_port", "last_seen": timestamp, "pin_hash_prefix": "prefix"}
        self.sock = None
        self.listening_thread = None
        self._running = False

    def start(self):
        """
        Starts listening for broadcasts in a separate thread.
        """
        if self._running:
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', BROADCAST_PORT))
        except socket.error as e:
            logger.error(f"Error binding listener socket: {e}", exc_info=True)
            if self.sock:
                self.sock.close()
                self.sock = None
            return

        self._running = True
        self.listening_thread = threading.Thread(target=self._listen_for_peers, daemon=True)
        self.listening_thread.start()
        logger.info(f"DiscoveryListener started for own_peer_id: {self.own_peer_id}.")

    def _listen_for_peers(self):
        """
        Continuously listens for incoming broadcast messages.
        """
        try:
            while self._running:
                try:
                    self.sock.settimeout(1.0) 
                    try:
                        data, addr = self.sock.recvfrom(1024)
                    except socket.timeout:
                        continue 

                    sender_ip = addr[0]
                    logger.debug(f"Received broadcast from {sender_ip}")

                    try:
                        message = json.loads(data.decode('utf-8'))
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode JSON from {sender_ip}: {data.decode('utf-8', errors='ignore')}")
                        continue

                    if message.get("app_id") != APP_ID:
                        logger.debug(f"Message from {sender_ip} has incorrect app_id: {message.get('app_id')}")
                        continue

                    if message.get("pin_hash_prefix") != self.current_pin_hash_prefix:
                        logger.debug(f"Message from {sender_ip} has different pin_hash_prefix. Their: {message.get('pin_hash_prefix')}, My: {self.current_pin_hash_prefix}")
                        # Remove if exists, as PIN prefix doesn't match anymore
                        removed_peer = self.discovered_peers.pop(message.get("peer_id"), None)
                        if removed_peer:
                            logger.info(f"Removed peer {message.get('peer_id')} due to PIN prefix mismatch.")
                        continue
                    
                    peer_id = message.get("peer_id")
                    service_port = message.get("service_port")
                    pin_hash_prefix_from_msg = message.get("pin_hash_prefix")

                    if not all([peer_id, isinstance(service_port, int), pin_hash_prefix_from_msg]):
                        logger.warning(f"Message from {sender_ip} is missing required fields: {message}")
                        continue

                    if peer_id == self.own_peer_id:
                        logger.debug(f"Ignoring own broadcast message from {peer_id}.")
                        continue
                    
                    if peer_id not in self.discovered_peers:
                         logger.info(f"New peer discovered: {peer_id} at {sender_ip}:{service_port} with matching PIN prefix.")
                    else:
                        logger.debug(f"Peer {peer_id} updated its presence.")
                    
                    self.discovered_peers[peer_id] = {
                        "address": f"{sender_ip}:{service_port}",
                        "last_seen": time.time(),
                        "pin_hash_prefix": pin_hash_prefix_from_msg
                    }

                except socket.error as e:
                    if self._running: 
                        logger.error(f"Socket error while listening: {e}", exc_info=True)
                    else:
                        logger.info("Listener socket error because listener is stopping.")
                    break 
                except Exception as e:
                    if self._running:
                        logger.error(f"Unexpected error in listener loop: {e}", exc_info=True)
                    # Depending on error, might want to break or continue
        except Exception as e:
            logger.critical(f"Unhandled exception in DiscoveryListener thread ({self.own_peer_id}): {e}", exc_info=True)
        finally:
            logger.info(f"DiscoveryListener thread ({self.own_peer_id}) finished.")


    def stop(self):
        """
        Stops the listening thread and closes the socket.
        """
        logger.info(f"Stopping DiscoveryListener for own_peer_id: {self.own_peer_id}.")
        self._running = False
        if self.sock:
            try:
                self.sock.close()
                logger.debug("Listener socket closed.")
            except Exception as e:
                logger.error(f"Error closing listener socket: {e}", exc_info=True)
            self.sock = None
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=2) 
        logger.info(f"DiscoveryListener stopped for own_peer_id: {self.own_peer_id}.")


    def get_peers(self, freshness_seconds: float = None) -> list:
        """
        Returns a list of discovered peers, optionally filtered by freshness.

        Args:
            freshness_seconds: How recent (in seconds) a peer's last_seen timestamp
                               should be to be included. Defaults to BROADCAST_INTERVAL_SECONDS * 3.

        Returns:
            A list of peer details dictionaries.
        """
        if freshness_seconds is None:
            freshness_seconds = BROADCAST_INTERVAL_SECONDS * 3

        current_time = time.time()
        fresh_peers = []
        stale_peers_ids = []

        # Iterate over a copy of items in case the dictionary is modified by the listener thread
        for peer_id, details in list(self.discovered_peers.items()): 
            if current_time - details["last_seen"] <= freshness_seconds:
                peer_info = details.copy()
                peer_info["peer_id"] = peer_id 
                fresh_peers.append(peer_info)
            else:
                stale_peers_ids.append(peer_id)
        
        # Clean up stale peers
        for peer_id in stale_peers_ids:
            if peer_id in self.discovered_peers: # Check if still exists (might be updated concurrently)
                del self.discovered_peers[peer_id]
                logger.info(f"Removed stale peer: {peer_id}")
        
        if stale_peers_ids and not fresh_peers:
            logger.info("No fresh peers remaining after cleanup.")
        elif not self.discovered_peers and not fresh_peers_list: # Assuming fresh_peers_list was from listener.get_peers()
             pass # No peers initially, no logging needed here for that.
             
        return fresh_peers

# Example Usage (for testing purposes, normally these classes would be used by the main app)
if __name__ == '__main__':
    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    
    my_peer_id = str(uuid.uuid4())
    my_service_port = 50001 
    my_pin = "1234" 
    import hashlib
    my_hashed_pin = hashlib.sha256(my_pin.encode('utf-8')).hexdigest()
    my_pin_hash_prefix = my_hashed_pin[:8]

    logger.info(f"My Peer ID: {my_peer_id}")
    logger.info(f"My Service Port: {my_service_port}")
    logger.info(f"My PIN Hash Prefix: {my_pin_hash_prefix}")

    broadcaster = DiscoveryBroadcaster(
        peer_id=my_peer_id,
        service_port=my_service_port,
        pin_hash_prefix=my_pin_hash_prefix
    )
    broadcaster.start()

    listener = DiscoveryListener(
        current_pin_hash_prefix=my_pin_hash_prefix,
        own_peer_id=my_peer_id
    )
    listener.start()

    try:
        for _ in range(10): # Run for a limited time for testing
            peers = listener.get_peers()
            logger.info(f"Discovered peers: {peers}")
            if not peers:
                logger.info("No peers found in this interval.")
            time.sleep(BROADCAST_INTERVAL_SECONDS / 2) # Check more frequently than broadcast interval
    except KeyboardInterrupt:
        logger.info("Shutting down example...")
    finally:
        broadcaster.stop()
        listener.stop()
        logger.info("Example cleanup complete.")
