"""
Main application window using customtkinter for the LAN File Sharer.
"""
import customtkinter
from customtkinter import CTkInputDialog # Ensure this specific import for CTkInputDialog
import tkinter # For filedialog
from tkinter import filedialog

# Core imports - adjust path as necessary if running app.py directly for testing vs as part of package
# Assuming standard package structure and running via main.py or python -m
try:
    from ..core import load_config, save_config, hash_pin
except ImportError:
    # Fallback for running app.py directly, assuming core is a sibling directory to ui's parent
    import sys
    import os
    # Get the absolute path to the project's root directory (lan_file_sharer)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    # Get the absolute path to the src directory
    src_path = os.path.join(project_root, 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    from core import load_config, save_config, hash_pin
    from core.network_discoverer import DiscoveryBroadcaster, DiscoveryListener, APP_ID, BROADCAST_PORT
    from core.file_client import FileClient

import uuid
import threading
import logging
# import queue 

logger = logging.getLogger(__name__)


class App(customtkinter.CTk):
    """
    The main application window class.
    Manages the overall UI structure and lifecycle, including configuration.
    """
    def __init__(self):
        """
        Initializes the main application window.
        Loads configuration, sets up UI elements for settings,
        and initializes core components.
        """
        super().__init__()

        self.title("LAN File Sharer")
        self.geometry("800x600")

        # Load configuration
        self.config = load_config()
        self.shared_folder_path = self.config.get("shared_folder_path", "Not set")
        self.hashed_pin = self.config.get("hashed_pin", None) # Store as None if not set

        # --- Main Layout Frames ---
        self.grid_columnconfigure(0, weight=1) # Configure column 0 to expand
        self.grid_rowconfigure(0, weight=0)    # Row for settings (fixed size)
        self.grid_rowconfigure(1, weight=1)    # Row for main content (expands)


        # --- Settings Frame ---
        self.settings_frame = customtkinter.CTkFrame(self)
        self.settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew") # Standardized pady
        self.settings_frame.grid_columnconfigure(0, weight=1) # Column for labels (takes available space)
        self.settings_frame.grid_columnconfigure(1, weight=0) # Column for buttons (fixed size)


        # Shared Folder UI
        self.folder_label_text = customtkinter.StringVar(value=f"Shared Folder: {self.shared_folder_path}")
        self.shared_folder_label = customtkinter.CTkLabel(
            self.settings_frame,
            textvariable=self.folder_label_text,
            anchor="w"
        )
        self.shared_folder_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew") # Standardized pady & sticky

        self.select_folder_button = customtkinter.CTkButton(
            self.settings_frame,
            text="Select Shared Folder",
            command=self._select_shared_folder
        )
        self.select_folder_button.grid(row=0, column=1, padx=10, pady=10, sticky="e") # Standardized pady

        # PIN UI
        self.pin_label_text = customtkinter.StringVar(value=self._get_pin_display_text())
        self.pin_label = customtkinter.CTkLabel(
            self.settings_frame,
            textvariable=self.pin_label_text,
            anchor="w"
        )
        self.pin_label.grid(row=1, column=0, padx=10, pady=10, sticky="ew") # Standardized pady & sticky

        self.set_pin_button = customtkinter.CTkButton(
            self.settings_frame,
            text="Set/Change PIN",
            command=self._set_pin
        )
        self.set_pin_button.grid(row=1, column=1, padx=10, pady=10, sticky="e") # Standardized pady
        
        self.main_content_frame = customtkinter.CTkFrame(self, fg_color="transparent") # Make transparent
        self.main_content_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew") # Standardized pady
        # --- Peer Discovery & File Browsing Attributes ---
        self.peer_id = str(uuid.uuid4())
        self.file_client = FileClient(current_full_pin_hash=self.hashed_pin) 
        self.discovery_listener = None
        self.discovery_broadcaster = None
        self.discovered_peers_cache = {} 
        self.selected_peer_id = None # Store selected peer's ID to fetch details from cache
        self.current_remote_path = "/" 
        self.service_port = 8080 # Placeholder for actual file server port

        # --- UI Elements for Peer Display & File Browsing (Layout already defined in previous turn) ---
        # Main content frame will now be split using a PanedWindow or just gridded frames
        # Let's use gridded frames for simplicity first.

        self.main_content_frame.grid_rowconfigure(0, weight=1) # Ensure row 0 of main_content_frame expands
        self.main_content_frame.grid_columnconfigure(0, weight=1) # Peers list
        self.main_content_frame.grid_columnconfigure(1, weight=2) 
        self.main_content_frame.grid_columnconfigure(2, weight=0) 

        # Theme colors for Listbox
        # These are common names; actual names might differ or need specific component parts.
        # Using ThemeManager to get colors for the current mode (light/dark).
        listbox_bg_color = customtkinter.ThemeManager.theme["CTkFrame"]["fg_color"]
        listbox_fg_color = customtkinter.ThemeManager.theme["CTkLabel"]["text_color"]
        listbox_select_bg_color = customtkinter.ThemeManager.theme["CTkButton"]["fg_color"] # Using button color for selection
        listbox_select_fg_color = customtkinter.ThemeManager.theme["CTkButton"]["text_color"]


        # Peers Frame
        self.peers_frame = customtkinter.CTkFrame(self.main_content_frame, fg_color="transparent")
        self.peers_frame.grid(row=0, column=0, padx=(0,5), pady=0, sticky="nsew")
        self.peers_frame.grid_rowconfigure(1, weight=1)
        self.peers_frame.grid_columnconfigure(0, weight=1)

        self.peers_label = customtkinter.CTkLabel(self.peers_frame, text="Discovered Peers:")
        self.peers_label.grid(row=0, column=0, padx=5, pady=(0,5), sticky="ew") # Adjusted pady
        
        self.peers_listbox = tkinter.Listbox(
            self.peers_frame, 
            selectmode=tkinter.SINGLE,
            bg=listbox_bg_color, 
            fg=listbox_fg_color, 
            selectbackground=listbox_select_bg_color,
            selectforeground=listbox_select_fg_color,
            relief="flat", 
            borderwidth=0, # Changed borderwidth to 0 for flatter look
            highlightthickness=1, # Add a subtle border using highlight
            highlightbackground=customtkinter.ThemeManager.theme["CTkFrame"]["border_color"],
            highlightcolor=customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]
        ) 
        self.peers_listbox.grid(row=1, column=0, padx=0, pady=0, sticky="nsew") # Adjusted padx/pady
        self.peers_listbox.bind("<<ListboxSelect>>", self._on_peer_selected)

        # Remote Files Frame
        self.remote_files_frame = customtkinter.CTkFrame(self.main_content_frame, fg_color="transparent") # Transparent to blend
        self.remote_files_frame.grid(row=0, column=1, padx=5, pady=0, sticky="nsew") # Standardized padx
        self.remote_files_frame.grid_rowconfigure(1, weight=1)
        self.remote_files_frame.grid_columnconfigure(0, weight=1)
        
        self.remote_path_label_text = customtkinter.StringVar(value=f"Files on peer: {self.current_remote_path}")
        self.remote_files_label = customtkinter.CTkLabel(self.remote_files_frame, textvariable=self.remote_path_label_text)
        self.remote_files_label.grid(row=0, column=0, padx=5, pady=(0,5), sticky="ew") # Adjusted pady

        self.remote_files_listbox = tkinter.Listbox(
            self.remote_files_frame,
            selectmode=tkinter.SINGLE,
            bg=listbox_bg_color, 
            fg=listbox_fg_color, 
            selectbackground=listbox_select_bg_color,
            selectforeground=listbox_select_fg_color,
            relief="flat", 
            borderwidth=0, # Changed borderwidth to 0
            highlightthickness=1,
            highlightbackground=customtkinter.ThemeManager.theme["CTkFrame"]["border_color"],
            highlightcolor=customtkinter.ThemeManager.theme["CTkButton"]["fg_color"]
        )
        self.remote_files_listbox.grid(row=1, column=0, padx=0, pady=0, sticky="nsew") # Adjusted padx/pady
        self.remote_files_listbox.bind("<Double-1>", self._on_remote_item_activated)

        # Download Button Frame (within main_content_frame, to the right of remote_files)
        self.download_button_frame = customtkinter.CTkFrame(self.main_content_frame, fg_color="transparent")
        self.download_button_frame.grid(row=0, column=2, padx=(5,0), pady=0, sticky="ns") # Align to top-center of its space
        self.download_button_frame.grid_rowconfigure(0, weight=0) 

        self.download_button = customtkinter.CTkButton(
            self.download_button_frame,
            text="Download Selected"
            # command is already set
        )
        self.download_button.grid(row=0, column=0, padx=5, pady=10, sticky="ew")
        
        self.remote_parent_dir_button = customtkinter.CTkButton(
            self.remote_files_frame, 
            text="Up One Level"
            # command is already set
        )
        self.remote_parent_dir_button.grid(row=2, column=0, padx=0, pady=(5,0), sticky="ew") # Adjusted padx/pady

        # Status Bar
        self.status_bar_text = customtkinter.StringVar(value="Status: Initializing...")
        self.status_bar = customtkinter.CTkLabel(self, textvariable=self.status_bar_text, anchor="w")
        self.status_bar.grid(row=2, column=0, padx=10, pady=(5,5), sticky="ew") 

        # Start discovery if config allows
        if self.hashed_pin and self.shared_folder_path != "Not set":
            self.after(100, self._start_discovery)
        else:
            msg = "Status: Please set PIN and Shared Folder to start discovery."
            logger.info(msg)
            self.status_bar_text.set(msg)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)


    def _get_pin_display_text(self) -> str:
        """Returns the display text for the PIN label."""
        return "PIN: ****" if self.hashed_pin else "PIN: Not set"

    def _select_shared_folder(self):
        """Opens a dialog to select the shared folder and updates configuration."""
        logger.debug("'_select_shared_folder' called.")
        try:
            new_folder = filedialog.askdirectory()
            if new_folder: 
                self.shared_folder_path = new_folder
                self.folder_label_text.set(f"Shared Folder: {self.shared_folder_path}")
                self._save_current_config()
                logger.info(f"User selected new shared folder: {self.shared_folder_path}")
                if self.hashed_pin:
                    self._restart_discovery()
            else:
                logger.info("User cancelled folder selection.")
        except Exception as e:
            logger.exception("Error in _select_shared_folder.")
            tkinter.messagebox.showerror("Error", f"Failed to select folder: {e}")
            self.status_bar_text.set("Status: Error selecting folder.")


    def _set_pin(self):
        """Opens a dialog to set/change the PIN and updates configuration."""
        logger.debug("'_set_pin' called.")
        try:
            dialog = CTkInputDialog(text="Enter a 4-digit PIN:", title="Set PIN")
            pin_input = dialog.get_input()

            if pin_input is None: # User cancelled
                logger.info("User cancelled PIN input.")
                return

            if len(pin_input) == 4 and pin_input.isdigit():
                new_hashed_pin = hash_pin(pin_input) # hash_pin logs its own errors
                if self.hashed_pin != new_hashed_pin:
                    self.hashed_pin = new_hashed_pin
                    self.pin_label_text.set(self._get_pin_display_text())
                    self._save_current_config()
                    self.file_client.update_pin_hash(self.hashed_pin) 
                    logger.info(f"User set new PIN. Hash prefix: {self.hashed_pin[:8]}...")
                    self._restart_discovery() 
                else:
                    logger.info("User entered the same PIN. No changes made.")
                    tkinter.messagebox.showinfo("PIN Not Changed", "The new PIN is the same as the current one.")
            else:
                logger.warning(f"Invalid PIN input by user: '{pin_input}'")
                tkinter.messagebox.showerror("Invalid PIN", "PIN must be exactly 4 digits.")
        except ValueError as ve: # From hash_pin
             logger.error(f"Error hashing PIN: {ve}", exc_info=True) # Already logged by hash_pin, but good to log context
             tkinter.messagebox.showerror("PIN Error", f"Invalid PIN entered: {ve}")
        except Exception as e:
            logger.exception("Error in _set_pin.")
            tkinter.messagebox.showerror("Error", f"Failed to set PIN: {e}")
            self.status_bar_text.set("Status: Error setting PIN.")


    def _save_current_config(self):
        """Saves the current shared folder path and hashed PIN to the config file."""
        logger.debug("'_save_current_config' called.")
        config_to_save = {
            "shared_folder_path": self.shared_folder_path,
            "hashed_pin": self.hashed_pin
        }
        try:
            save_config(config_to_save) # save_config now handles its own logging
            logger.info(f"Configuration saved: Shared Folder='{self.shared_folder_path}', PIN Hash Set={'Yes' if self.hashed_pin else 'No'}")
            self.status_bar_text.set("Status: Configuration saved.")
        except Exception as e:
            logger.exception("Failed to save configuration from UI.")
            tkinter.messagebox.showerror("Configuration Error", f"Failed to save configuration: {e}")
            self.status_bar_text.set("Status: Error saving configuration.")


    def _restart_discovery(self):
        """Stops and restarts the discovery services. Useful after PIN/config changes."""
        logger.info("Restarting discovery services...")
        self._stop_discovery()
        if self.hashed_pin and self.shared_folder_path != "Not set":
            self._start_discovery()
        else:
            msg = "Status: Cannot start discovery. PIN or Shared Folder not set."
            logger.warning(msg)
            self.status_bar_text.set(msg)


    def _start_discovery(self):
        """Initializes and starts the discovery listener and broadcaster."""
        logger.info("Attempting to start discovery services...")
        if not self.hashed_pin or self.shared_folder_path == "Not set":
            msg = "Discovery not started: PIN or Shared Folder not set."
            logger.warning(msg)
            self.status_bar_text.set(f"Status: {msg}")
            return

        pin_hash_prefix = self.hashed_pin[:8]
        logger.info(f"Starting discovery with PIN hash prefix: {pin_hash_prefix} and Peer ID: {self.peer_id[:8]}...")
        
        try:
            self.discovery_listener = DiscoveryListener(
                current_pin_hash_prefix=pin_hash_prefix,
                own_peer_id=self.peer_id
            )
            self.discovery_listener.start() # Listener logs its own startup

            # TODO: Update self.service_port when FileServer integration is complete
            self.discovery_broadcaster = DiscoveryBroadcaster(
                peer_id=self.peer_id,
                service_port=self.service_port, 
                pin_hash_prefix=pin_hash_prefix
            )
            self.discovery_broadcaster.start() # Broadcaster logs its own startup
            
            self.status_bar_text.set(f"Status: Discovery active. My Peer ID: {self.peer_id[:8]}...")
            self._update_peers_ui() # Start periodic UI update for peers
            logger.info("Discovery services started successfully.")

        except Exception as e:
            logger.exception("Error starting discovery services from UI.")
            self.status_bar_text.set(f"Status: Error starting discovery: {e}")
            if self.discovery_listener: self.discovery_listener.stop()
            if self.discovery_broadcaster: self.discovery_broadcaster.stop()
            self.discovery_listener = None
            self.discovery_broadcaster = None


    def _stop_discovery(self):
        """Stops the discovery listener and broadcaster."""
        logger.info("Attempting to stop discovery services...")
        try:
            if self.discovery_listener:
                self.discovery_listener.stop() # Listener logs its own shutdown
                self.discovery_listener = None
            if self.discovery_broadcaster:
                self.discovery_broadcaster.stop() # Broadcaster logs its own shutdown
                self.discovery_broadcaster = None
            self.status_bar_text.set("Status: Discovery stopped.")
            logger.info("Discovery services stopped.")
        except Exception as e:
            logger.exception("Error stopping discovery services from UI.")
            self.status_bar_text.set("Status: Error stopping discovery.")


    def _on_closing(self):
        """Handles cleanup when the application window is closed."""
        logger.info("Application closing sequence started...")
        try:
            self._stop_discovery()
            # TODO: Add FileServer stop here when integrated
        except Exception as e:
            logger.exception("Error during pre-shutdown cleanup.")
        finally:
            logger.info("Destroying main window.")
            self.destroy()

    def _update_peers_ui(self):
        """Periodically updates the list of discovered peers in the UI."""
        # This method is complex and already modified in a previous subtask.
        # For now, just adding a try-except around its core logic and basic logging.
        # logger.debug("'_update_peers_ui' called.") # Too verbose for periodic
        if not self.discovery_listener:
            # This state is normal if discovery hasn't started or is stopped.
            # logger.debug("Discovery listener not active, skipping peer UI update.")
            self.peers_listbox.delete(0, tkinter.END) # Clear list if no listener
            return
        
        try:
            fresh_peers_list = self.discovery_listener.get_peers() 
            
            # Store current selection to try and restore it
            selected_indices_before_update = self.peers_listbox.curselection()
            selected_peer_id_to_restore = None
            if selected_indices_before_update and self.selected_peer_id:
                 # Check if the currently selected peer_id is still in the new fresh list
                is_still_fresh = any(p['peer_id'] == self.selected_peer_id for p in fresh_peers_list)
                if is_still_fresh:
                    selected_peer_id_to_restore = self.selected_peer_id
                else: # Selected peer is no longer fresh, clear dependent UI
                    self.selected_peer_id = None 
                    self.remote_files_listbox.delete(0, tkinter.END)
                    self.remote_path_label_text.set("Files on peer: ")


            current_listbox_items_map = {} # Maps display_text to peer_id
            for i in range(self.peers_listbox.size()):
                display_text = self.peers_listbox.get(i)
                # This reverse mapping is still a bit fragile.
                # Find peer_id for this display_text from current cache
                for pid, details in self.discovered_peers_cache.items():
                    if display_text == f"{pid[:8]}... ({details['address']})":
                        current_listbox_items_map[display_text] = pid
                        break
            
            new_discovered_peers_cache_temp = {p["peer_id"]: p for p in fresh_peers_list}
            
            # Update listbox content
            self.peers_listbox.delete(0, tkinter.END)
            
            sorted_peers_to_display = sorted(
                [(f"{p['peer_id'][:8]}... ({p['address']})", p['peer_id']) for p in fresh_peers_list],
                key=lambda x: x[0] # Sort by display text
            )

            new_selection_index = None
            for index, (display_text, peer_id) in enumerate(sorted_peers_to_display):
                self.peers_listbox.insert(tkinter.END, display_text)
                if peer_id == selected_peer_id_to_restore:
                    new_selection_index = index
            
            if new_selection_index is not None:
                self.peers_listbox.selection_set(new_selection_index)
                self.peers_listbox.activate(new_selection_index)
            
            self.discovered_peers_cache = new_discovered_peers_cache_temp # Update main cache

            if not fresh_peers_list:
                self.peers_listbox.insert(tkinter.END, "No peers found yet...")
            
            # Update status bar based on whether discovery is active, not just listener object presence
            if self.discovery_broadcaster and self.discovery_listener: # Check both
                 status_msg_prefix = f"Status: Discovery active. My Peer ID: {self.peer_id[:8]}..."
                 status_msg_suffix = f" Found {len(fresh_peers_list)} peer(s)." if fresh_peers_list else " No peers found."
                 self.status_bar_text.set(status_msg_prefix + status_msg_suffix)
            else:
                 self.status_bar_text.set("Status: Discovery inactive.")


        except Exception as e:
            logger.exception("Error updating peers UI.")
            self.status_bar_text.set("Status: Error updating peer list.")
        
        # Schedule next update
        self.after(5000, self._update_peers_ui) 


    def _on_peer_selected(self, event=None): 
        """Handles selection of a peer from the listbox."""
        # logger.debug("'_on_peer_selected' called.") # Can be verbose
        selected_indices = self.peers_listbox.curselection()
        if not selected_indices:
            self.selected_peer_id = None # Clear selection
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_path_label_text.set("Files on peer: ")
            logger.debug("Peer selection cleared.")
            return

        selected_index = selected_indices[0]
        selected_display_text = self.peers_listbox.get(selected_index)
        logger.info(f"User selected peer from listbox: '{selected_display_text}'")

        found_peer_id = None
        # Find peer_id from display_text using the updated cache
        for pid, details in self.discovered_peers_cache.items():
            if selected_display_text == f"{pid[:8]}... ({details['address']})":
                found_peer_id = pid
                break
        
        if found_peer_id:
            self.selected_peer_id = found_peer_id
            peer_details = self.discovered_peers_cache[found_peer_id]
            self.current_remote_path = "/" 
            logger.info(f"Loading files for selected peer {self.selected_peer_id[:8]} at address {peer_details['address']}")
            self.status_bar_text.set(f"Status: Selected peer {self.selected_peer_id[:8]}. Loading files...")
            self._load_remote_files(peer_details["address"], self.current_remote_path)
        else:
            logger.error(f"Could not find peer_id for selected display text: {selected_display_text}. Cache: {self.discovered_peers_cache}")
            self.selected_peer_id = None
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_path_label_text.set("Files on peer: Error resolving peer")
            self.status_bar_text.set("Status: Error selecting peer.")
            tkinter.messagebox.showerror("Error", "Could not resolve selected peer. Please try again.")


    def _load_remote_files(self, peer_address: str, remote_path: str = "/"):
        """Loads and displays files from the selected peer and path."""
        logger.info(f"Attempting to load remote files from {peer_address}{remote_path}")
        if not self.file_client or not self.hashed_pin:
            msg = "PIN not set. Cannot browse files."
            logger.warning(f"_load_remote_files called but {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_files_listbox.insert(tkinter.END, f"Cannot load files: {msg}")
            tkinter.messagebox.showwarning("PIN Required", "A PIN must be set to browse remote files.")
            return
        
        self.remote_path_label_text.set(f"Files on {peer_address}{remote_path} (Loading...)")
        self.remote_files_listbox.delete(0, tkinter.END)
        self.remote_files_listbox.insert(tkinter.END, "Loading...")

        self.file_client.update_pin_hash(self.hashed_pin) # Ensure client has latest PIN

        def _list_files_thread():
            try:
                logger.debug(f"Thread started: list_files for {peer_address}{remote_path}")
                result = self.file_client.list_files(peer_address, remote_path) # This now returns dict with "error" on failure
                self.after(0, self._update_remote_files_ui, result, peer_address, remote_path)
            except Exception as e: # Catch any unexpected error in thread
                logger.critical(f"Unhandled exception in _list_files_thread for {peer_address}{remote_path}: {e}", exc_info=True)
                # Schedule UI update with error
                self.after(0, self._update_remote_files_ui, {"error": f"Unexpected client error: {e}"}, peer_address, remote_path)
        
        threading.Thread(target=_list_files_thread, daemon=True).start()


    def _update_remote_files_ui(self, listing_result: dict, peer_address:str, remote_path:str):
        """Callback to update the remote files listbox with results."""
        logger.debug(f"Updating remote files UI for {peer_address}{remote_path}. Result: {listing_result}")
        self.remote_files_listbox.delete(0, tkinter.END) 

        if "error" in listing_result:
            error_msg = listing_result['error']
            logger.error(f"Failed to list files for {peer_address}{remote_path}: {error_msg}")
            self.remote_files_listbox.insert(tkinter.END, f"Error: {error_msg}")
            self.remote_path_label_text.set(f"Files on {peer_address}{remote_path} (Error)")
            self.status_bar_text.set(f"Status: Error listing files from peer.")
            # Don't show a messagebox here as it could be annoying if it happens frequently
            return

        self.current_remote_path = listing_result.get("path", remote_path) 
        self.remote_path_label_text.set(f"Files on {peer_address}{self.current_remote_path}")
        self.status_bar_text.set(f"Status: Files loaded from {peer_address}{self.current_remote_path}")
        logger.info(f"Remote files UI updated for path: {self.current_remote_path}")

        if self.current_remote_path != "/" and self.current_remote_path != "":
            self.remote_files_listbox.insert(tkinter.END, ".. (Parent Directory)")

        for dirname in sorted(listing_result.get("directories", [])):
            self.remote_files_listbox.insert(tkinter.END, f"[D] {dirname}")
        for filename in sorted(listing_result.get("files", [])):
            self.remote_files_listbox.insert(tkinter.END, filename)

        if not listing_result.get("directories") and not listing_result.get("files"):
            if self.current_remote_path == "/": 
                 self.remote_files_listbox.insert(tkinter.END, "(This directory is empty)")


    def _on_remote_item_activated(self, event=None):
        """Handles double-click on a remote file/folder or Enter key."""
        # logger.debug("'_on_remote_item_activated' called.") # Can be verbose
        selected_indices = self.remote_files_listbox.curselection()
        if not selected_indices:
            logger.debug("No item selected in remote_files_listbox for activation.")
            return
        selected_item_text = self.remote_files_listbox.get(selected_indices[0])
        logger.info(f"User activated remote item: '{selected_item_text}'")

        if not self.selected_peer_id:
            msg = "No peer selected to browse."
            logger.warning(f"_on_remote_item_activated called but {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showwarning("No Peer Selected", msg)
            return
        
        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
            msg = "Selected peer details not found. Please reselect peer."
            logger.error(f"_on_remote_item_activated: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showerror("Error", msg)
            return
        peer_address = peer_details["address"]

        new_path_str = "" # Use string for path to be passed to _load_remote_files
        try:
            if selected_item_text == ".. (Parent Directory)":
                new_path_str = Path(self.current_remote_path).parent.as_posix()
                if new_path_str == ".": new_path_str = "/" 
            elif selected_item_text.startswith("[D] "):
                dirname = selected_item_text[4:]
                new_path_str = Path(self.current_remote_path).joinpath(dirname).as_posix()
                # Normalize slashes for URLs (as_posix does this)
                if not new_path_str.startswith("/"): new_path_str = "/" + new_path_str # Ensure leading slash
            else: # It's a file, so attempt download
                logger.info(f"Item '{selected_item_text}' is a file, initiating download.")
                self._download_selected_file()
                return 

            logger.info(f"Navigating to new remote path: {new_path_str} on {peer_address}")
            self.status_bar_text.set(f"Status: Navigating to {new_path_str} on {peer_address}...")
            self._load_remote_files(peer_address, new_path_str)
        except Exception as e:
            logger.exception(f"Error processing remote item activation for '{selected_item_text}'.")
            tkinter.messagebox.showerror("Navigation Error", f"Could not process selection: {e}")
            self.status_bar_text.set("Status: Error navigating remote files.")


    def _download_selected_file(self):
        """Downloads the selected file from the remote peer."""
        logger.debug("'_download_selected_file' called.")
        selected_indices = self.remote_files_listbox.curselection()
        if not selected_indices:
            msg = "No file selected for download."
            logger.warning(f"_download_selected_file: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showinfo("Download", msg)
            return
        
        selected_item_text = self.remote_files_listbox.get(selected_indices[0])
        logger.info(f"User initiated download for remote item: '{selected_item_text}'")

        if selected_item_text.startswith("[D] ") or selected_item_text == ".. (Parent Directory)":
            msg = "Cannot download a directory. Please select a file."
            logger.warning(f"_download_selected_file: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showwarning("Download Error", msg)
            return

        if not self.selected_peer_id:
            msg = "No peer selected to download from."
            logger.warning(f"_download_selected_file: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showwarning("No Peer Selected", msg)
            return
        
        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
            msg = "Selected peer details not found. Please reselect peer."
            logger.error(f"_download_selected_file: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showerror("Error", msg)
            return
        peer_address = peer_details["address"]
        
        remote_file_path = Path(self.current_remote_path).joinpath(selected_item_text).as_posix()
        if not remote_file_path.startswith("/"): remote_file_path = "/" + remote_file_path


        local_save_path = filedialog.asksaveasfilename(initialfile=selected_item_text)
        if not local_save_path:
            logger.info("User cancelled 'Save As' dialog for download.")
            self.status_bar_text.set("Status: Download cancelled by user.")
            return

        logger.info(f"Attempting to download '{remote_file_path}' from {peer_address} to '{local_save_path}'")
        self.status_bar_text.set(f"Status: Downloading {os.path.basename(remote_file_path)}...")

        self.file_client.update_pin_hash(self.hashed_pin) # Ensure latest PIN

        def _download_thread():
            try:
                logger.debug(f"Thread started: download_file for {remote_file_path}")
                success = self.file_client.download_file(peer_address, remote_file_path, local_save_path,
                                                         progress_callback=self._update_download_progress)
                # file_client.download_file now returns bool and logs its own errors
                self.after(0, self._on_download_complete, success, remote_file_path, local_save_path, None) # Pass None for error_msg initially
            except Exception as e:
                logger.critical(f"Unhandled exception in _download_thread for {remote_file_path}: {e}", exc_info=True)
                self.after(0, self._on_download_complete, False, remote_file_path, local_save_path, f"Unexpected client error: {e}")
        
        threading.Thread(target=_download_thread, daemon=True).start()


    def _update_download_progress(self, current_bytes: int, total_bytes: int):
        """Updates the status bar with download progress."""
        # logger.debug(f"Download progress: {current_bytes}/{total_bytes}") # Too verbose
        if total_bytes > 0:
            progress_percent = (current_bytes / total_bytes) * 100
            self.status_bar_text.set(f"Status: Downloading... {current_bytes // 1024}KB / {total_bytes // 1024}KB ({progress_percent:.1f}%)")
        else:
            self.status_bar_text.set(f"Status: Downloading... {current_bytes // 1024}KB (total size unknown)")


    def _on_download_complete(self, success: bool, remote_file: str, local_file: str, error_msg: str = None):
        """Callback for when download finishes."""
        base_remote_file = os.path.basename(remote_file)
        if success:
            logger.info(f"Successfully downloaded '{remote_file}' to '{local_file}'")
            self.status_bar_text.set(f"Status: Downloaded {base_remote_file} successfully!")
            tkinter.messagebox.showinfo("Download Complete", f"File '{os.path.basename(local_file)}' downloaded successfully to:\n{os.path.dirname(local_file)}")
        else:
            # Error should have been logged by FileClient or the download thread
            final_error_msg = error_msg or "Failed to download file. Check logs for details." 
            logger.error(f"Failed to download '{remote_file}' to '{local_file}'. Reported error: {final_error_msg}")
            self.status_bar_text.set(f"Status: Failed to download {base_remote_file}. Error: {final_error_msg.split('.')[0]}") # Short error for status
            tkinter.messagebox.showerror("Download Failed", f"Failed to download '{base_remote_file}'.\nError: {final_error_msg}")


    def _go_to_parent_directory(self):
        """Navigates the remote file list to the parent of the current remote path."""
        logger.debug("'_go_to_parent_directory' called.")
        if not self.selected_peer_id:
            msg = "No peer selected to navigate."
            logger.warning(f"_go_to_parent_directory: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showwarning("No Peer Selected", msg)
            return

        if self.current_remote_path == "/" or self.current_remote_path == "":
            logger.info("Already at the root directory. Cannot go to parent.")
            self.status_bar_text.set("Status: Already at the root directory.")
            return

        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
            msg = "Selected peer details not found. Please reselect peer."
            logger.error(f"_go_to_parent_directory: {msg.lower()}")
            self.status_bar_text.set(f"Status: {msg}")
            tkinter.messagebox.showerror("Error", msg)
            return
        peer_address = peer_details["address"]

        try:
            parent_path_str = Path(self.current_remote_path).parent.as_posix()
            if parent_path_str == ".": parent_path_str = "/" 
            if not parent_path_str.startswith("/"): parent_path_str = "/" + parent_path_str


            logger.info(f"Navigating to parent directory: {parent_path_str} on {peer_address}")
            self.status_bar_text.set(f"Status: Navigating to parent directory {parent_path_str} on {peer_address}...")
            self._load_remote_files(peer_address, parent_path_str)
        except Exception as e:
            logger.exception(f"Error calculating parent directory from '{self.current_remote_path}'.")
            tkinter.messagebox.showerror("Navigation Error", f"Could not determine parent directory: {e}")
            self.status_bar_text.set("Status: Error navigating to parent directory.")
        
        # Create a temporary mapping from a display string to peer_id for easier lookup
        # This assumes peer_id is unique and suitable for display or part of display text.
        # For display, we might want something like "PeerName (IP_Address)" if we add names later.
        # For now, using peer_id (or its prefix) and address.
        
        new_discovered_peers_cache = {}
        peers_to_display = []

        for peer_details in fresh_peers_list:
            peer_id = peer_details["peer_id"]
            new_discovered_peers_cache[peer_id] = peer_details # Update cache
            
            # Display format: Using first 8 chars of peer_id and its address
            # Address is "ip:service_port"
            display_text = f"{peer_id[:8]}... ({peer_details['address']})"
            peers_to_display.append((display_text, peer_id)) # Store tuple (display_text, peer_id)

        # Sort peers for consistent display
        peers_to_display.sort()

        # --- Efficiently update listbox ---
        # 1. Remove peers from listbox that are no longer fresh
        # We need to map display_text back to peer_id to check against fresh_peers_list
        # This is tricky if display_text is not unique or if peer_id isn't directly in listbox.
        # A simpler approach for now: clear and repopulate.
        # For more complex scenarios, keeping a direct map of listbox_index to peer_id is better.
        
        # Store current selection to try and restore it
        selected_indices = self.peers_listbox.curselection()
        selected_peer_id_to_restore = None
        if selected_indices:
            # Assuming listbox stores display_text, and we need to find its corresponding peer_id
            # This requires a reverse lookup from the old cache or a more direct mapping.
            # For now, let's simplify: if the selected_peer_id is still in fresh_peers, reselect it.
            if self.selected_peer_id and self.selected_peer_id in new_discovered_peers_cache:
                selected_peer_id_to_restore = self.selected_peer_id
        
        self.peers_listbox.delete(0, tkinter.END)
        self.discovered_peers_cache = new_discovered_peers_cache # Update the main cache

        new_selection_index = None
        for index, (display_text, peer_id) in enumerate(peers_to_display):
            self.peers_listbox.insert(tkinter.END, display_text)
            if peer_id == selected_peer_id_to_restore:
                new_selection_index = index
        
        if new_selection_index is not None:
            self.peers_listbox.selection_set(new_selection_index)
            self.peers_listbox.activate(new_selection_index) # Ensure it's visible

        if not fresh_peers_list:
            self.peers_listbox.insert(tkinter.END, "No peers found yet...")
            self.status_bar_text.set(f"Status: Discovery active. My Peer ID: {self.peer_id[:8]}... No peers found.")
        else:
             self.status_bar_text.set(f"Status: Discovery active. My Peer ID: {self.peer_id[:8]}... Found {len(fresh_peers_list)} peer(s).")

        # Schedule next update
        self.after(5000, self._update_peers_ui) # Update every 5 seconds


    def _on_peer_selected(self, event=None): # Added event=None for direct calls
        """Handles selection of a peer from the listbox."""
        selected_indices = self.peers_listbox.curselection()
        if not selected_indices:
            self.selected_peer_id = None
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_path_label_text.set("Files on peer: ")
            return

        selected_index = selected_indices[0]
        selected_display_text = self.peers_listbox.get(selected_index)

        # Find the peer_id from the display_text. This is a bit fragile.
        # Assumes display_text format: "peer_id_prefix... (address)"
        # A better way would be to store (display_text, peer_id) in listbox or have a direct map.
        # For now, iterate through cache:
        found_peer_id = None
        for pid, details in self.discovered_peers_cache.items():
            if selected_display_text == f"{pid[:8]}... ({details['address']})":
                found_peer_id = pid
                break
        
        if found_peer_id:
            self.selected_peer_id = found_peer_id
            peer_details = self.discovered_peers_cache[found_peer_id]
            self.current_remote_path = "/" # Reset to root when a new peer is selected
            self.status_bar_text.set(f"Status: Selected peer {self.selected_peer_id[:8]}. Loading files...")
            self._load_remote_files(peer_details["address"], self.current_remote_path)
        else:
            print(f"Error: Could not find peer_id for selected display text: {selected_display_text}")
            self.selected_peer_id = None
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_path_label_text.set("Files on peer: Error resolving peer")
            self.status_bar_text.set("Status: Error selecting peer.")


    def _load_remote_files(self, peer_address: str, remote_path: str = "/"):
        """Loads and displays files from the selected peer and path."""
        if not self.file_client or not self.hashed_pin:
            self.status_bar_text.set("Status: PIN not set. Cannot browse files.")
            self.remote_files_listbox.delete(0, tkinter.END)
            self.remote_files_listbox.insert(tkinter.END, "Cannot load files: PIN not set.")
            return
        
        self.remote_path_label_text.set(f"Files on {peer_address}{remote_path} (Loading...)")
        self.remote_files_listbox.delete(0, tkinter.END)
        self.remote_files_listbox.insert(tkinter.END, "Loading...")

        # Ensure file_client has the latest PIN hash (could have changed)
        self.file_client.update_pin_hash(self.hashed_pin)

        try:
            # Offload network request to a thread to avoid freezing UI
            # For complex apps, a queue for results would be better.
            # For now, using `self.after` to check results if simple, or direct update from thread.
            # Let's try direct update from thread via self.after for simplicity here.
            
            def _list_files_thread():
                result = self.file_client.list_files(peer_address, remote_path)
                self.after(0, self._update_remote_files_ui, result, peer_address, remote_path)

            threading.Thread(target=_list_files_thread, daemon=True).start()

        except Exception as e: # Should not happen if threading is correct
            print(f"Error in _load_remote_files before threading: {e}")
            self.status_bar_text.set(f"Status: Error preparing to list files: {e}")
            self._update_remote_files_ui({"error": f"Client-side error: {e}"}, peer_address, remote_path)


    def _update_remote_files_ui(self, listing_result: dict, peer_address:str, remote_path:str):
        """Callback to update the remote files listbox with results."""
        self.remote_files_listbox.delete(0, tkinter.END) # Clear "Loading..."

        if "error" in listing_result:
            error_msg = listing_result['error']
            self.remote_files_listbox.insert(tkinter.END, f"Error: {error_msg}")
            self.remote_path_label_text.set(f"Files on {peer_address}{remote_path} (Error)")
            self.status_bar_text.set(f"Status: Error listing files: {error_msg}")
            return

        self.current_remote_path = listing_result.get("path", remote_path) # Update current path
        self.remote_path_label_text.set(f"Files on {peer_address}{self.current_remote_path}")
        self.status_bar_text.set(f"Status: Files loaded from {peer_address}{self.current_remote_path}")

        # Add ".." for parent directory if not at root
        if self.current_remote_path != "/" and self.current_remote_path != "":
            self.remote_files_listbox.insert(tkinter.END, ".. (Parent Directory)")

        for dirname in sorted(listing_result.get("directories", [])):
            self.remote_files_listbox.insert(tkinter.END, f"[D] {dirname}")
        for filename in sorted(listing_result.get("files", [])):
            self.remote_files_listbox.insert(tkinter.END, filename)

        if not listing_result.get("directories") and not listing_result.get("files"):
            if self.current_remote_path == "/": # Only show if truly empty, not just ".." added
                 self.remote_files_listbox.insert(tkinter.END, "(This directory is empty)")


    def _on_remote_item_activated(self, event=None):
        """Handles double-click on a remote file/folder or Enter key."""
        selected_indices = self.remote_files_listbox.curselection()
        if not selected_indices:
            return
        selected_item_text = self.remote_files_listbox.get(selected_indices[0])

        if not self.selected_peer_id:
            self.status_bar_text.set("Status: No peer selected to browse.")
            return
        
        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
            self.status_bar_text.set("Status: Selected peer details not found.")
            return
        peer_address = peer_details["address"]

        new_path = ""
        if selected_item_text == ".. (Parent Directory)":
            new_path = Path(self.current_remote_path).parent.as_posix()
            if new_path == ".": new_path = "/" # Handle case where parent is root
        elif selected_item_text.startswith("[D] "):
            dirname = selected_item_text[4:]
            # Ensure correct path joining, especially for root
            if self.current_remote_path == "/":
                new_path = f"/{dirname}"
            else:
                new_path = f"{self.current_remote_path.rstrip('/')}/{dirname}"
        else: # It's a file, so attempt download
            self._download_selected_file()
            return # Don't try to navigate further

        self.status_bar_text.set(f"Status: Navigating to {new_path} on {peer_address}...")
        self._load_remote_files(peer_address, new_path)


    def _download_selected_file(self):
        """Downloads the selected file from the remote peer."""
        selected_indices = self.remote_files_listbox.curselection()
        if not selected_indices:
            self.status_bar_text.set("Status: No file selected for download.")
            return
        
        selected_item_text = self.remote_files_listbox.get(selected_indices[0])

        if selected_item_text.startswith("[D] ") or selected_item_text == ".. (Parent Directory)":
            self.status_bar_text.set("Status: Cannot download a directory. Please select a file.")
            return

        if not self.selected_peer_id:
            self.status_bar_text.set("Status: No peer selected to download from.")
            return
        
        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
            self.status_bar_text.set("Status: Selected peer details not found.")
            return
        peer_address = peer_details["address"]
        
        # Construct full remote file path
        # Ensure correct path joining, especially if current_remote_path is "/"
        if self.current_remote_path == "/":
            remote_file_path = f"/{selected_item_text}"
        else:
            remote_file_path = f"{self.current_remote_path.rstrip('/')}/{selected_item_text}"

        local_save_path = filedialog.asksaveasfilename(initialfile=selected_item_text)
        if not local_save_path:
            self.status_bar_text.set("Status: Download cancelled by user.")
            return

        self.status_bar_text.set(f"Status: Downloading {remote_file_path} to {local_save_path}...")

        # Ensure file_client has the latest PIN hash
        self.file_client.update_pin_hash(self.hashed_pin)

        try:
            # Progress bar can be added here later if CTk has a simple one, or via status bar updates
            def _download_thread():
                success = self.file_client.download_file(peer_address, remote_file_path, local_save_path,
                                                         progress_callback=self._update_download_progress)
                self.after(0, self._on_download_complete, success, remote_file_path, local_save_path)
            
            threading.Thread(target=_download_thread, daemon=True).start()

        except Exception as e: # Should not happen if threading is correct
            print(f"Error in _download_selected_file before threading: {e}")
            self.status_bar_text.set(f"Status: Error preparing download: {e}")
            self._on_download_complete(False, remote_file_path, local_save_path, error_msg=f"Client-side error: {e}")


    def _update_download_progress(self, current_bytes: int, total_bytes: int):
        """Updates the status bar with download progress."""
        if total_bytes > 0:
            progress_percent = (current_bytes / total_bytes) * 100
            self.status_bar_text.set(f"Status: Downloading... {current_bytes}/{total_bytes} bytes ({progress_percent:.2f}%)")
        else:
            self.status_bar_text.set(f"Status: Downloading... {current_bytes} bytes (total size unknown)")


    def _on_download_complete(self, success: bool, remote_file: str, local_file: str, error_msg: str = None):
        """Callback for when download finishes."""
        if success:
            self.status_bar_text.set(f"Status: Downloaded {remote_file} to {local_file} successfully!")
            tkinter.messagebox.showinfo("Download Complete", f"File '{os.path.basename(local_file)}' downloaded successfully to:\n{os.path.dirname(local_file)}")
        else:
            final_error_msg = error_msg or "Failed to download file." # Use provided error or default
            self.status_bar_text.set(f"Status: Failed to download {remote_file}. Error: {final_error_msg}")
            tkinter.messagebox.showerror("Download Failed", f"Failed to download '{os.path.basename(remote_file)}'.\nError: {final_error_msg}")


    def _go_to_parent_directory(self):
        """Navigates the remote file list to the parent of the current remote path."""
        if not self.selected_peer_id:
            self.status_bar_text.set("Status: No peer selected.")
            return

        if self.current_remote_path == "/" or self.current_remote_path == "":
            self.status_bar_text.set("Status: Already at the root directory.")
            return

        peer_details = self.discovered_peers_cache.get(self.selected_peer_id)
        if not peer_details:
             self.status_bar_text.set("Status: Selected peer details not found.")
             return
        peer_address = peer_details["address"]

        parent_path = Path(self.current_remote_path).parent.as_posix()
        if parent_path == ".": parent_path = "/" # Handle case where parent becomes root
        
        self.status_bar_text.set(f"Status: Navigating to parent directory {parent_path} on {peer_address}...")
        self._load_remote_files(peer_address, parent_path)


def run_app():
    """
    Sets up the customtkinter appearance and theme, then creates an instance
    of the App and starts the customtkinter event loop.
    """
    customtkinter.set_appearance_mode("system")  # Follow system light/dark mode
    customtkinter.set_default_color_theme("blue") # Use "blue" theme which is Win11-like

    app = App()
    app.mainloop()

if __name__ == '__main__':
    # This allows running the UI directly for testing/development
    # e.g., python -m lan_file_sharer.src.ui.app
    run_app()
