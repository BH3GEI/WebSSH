import os
import json
import select
import threading
import logging
from flask import Flask, render_template, request, redirect, url_for
from flask_sock import Sock
import paramiko

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO) # Use DEBUG for more verbose output
CONFIG_FILE = 'config.json'
BUFFER_SIZE = 1024 * 16 # 16KB buffer for SSH data

# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Needed for flash messages, etc.
sock = Sock(app)

# --- Helper Functions ---
def load_config():
    """Loads SSH config from JSON file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure essential keys exist with defaults
            config.setdefault('hostname', '')
            config.setdefault('port', 22)
            config.setdefault('username', '')
            config.setdefault('password', '')
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning(f"Config file '{CONFIG_FILE}' not found or invalid. Using defaults.")
        # Return default structure if file missing or invalid
        return {'hostname': '', 'port': 22, 'username': '', 'password': ''}

def save_config(config):
    """Saves SSH config to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logging.info(f"Configuration saved to {CONFIG_FILE}")
        return True
    except IOError as e:
        logging.error(f"Error saving config file: {e}")
        return False

# --- SSH Interaction Logic (within WebSocket context) ---
def ssh_interaction(ws, config):
    """Handles the SSH connection and data transfer."""
    ssh = None
    channel = None
    try:
        # 1. Check Config
        if not all([config.get('hostname'), config.get('username')]):
             ws.send(json.dumps({"type": "error", "data": "Hostname and Username are required in config."}))
             logging.warning("SSH connection aborted: Missing hostname or username in config.")
             return # Exit the function, WS will be closed by caller

        hostname = config['hostname']
        port = int(config.get('port', 22))
        username = config['username']
        password = config.get('password', '') # Allow empty password for key auth (though not fully implemented here)

        # 2. Establish SSH Connection
        logging.info(f"Attempting SSH connection to {username}@{hostname}:{port}")
        ws.send(json.dumps({"type": "status", "data": f"Connecting to {username}@{hostname}:{port}..."}))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # WARNING: Insecure, accepts unknown host keys

        try:
             # Consider adding timeout parameter: ssh.connect(..., timeout=10)
             ssh.connect(hostname, port=port, username=username, password=password, look_for_keys=True) # look_for_keys=True allows trying key auth
        except paramiko.AuthenticationException:
             logging.warning(f"Authentication failed for {username}@{hostname}")
             ws.send(json.dumps({"type": "error", "data": "Authentication failed (Incorrect password or key?)."}))
             return
        except Exception as e:
             logging.error(f"SSH connection error to {hostname}:{port}: {e}")
             ws.send(json.dumps({"type": "error", "data": f"Connection Error: {e}"}))
             return

        logging.info(f"SSH connection established to {username}@{hostname}")
        ws.send(json.dumps({"type": "status", "data": "SSH Connected."}))

        # 3. Open SSH Shell Channel
        channel = ssh.invoke_shell()
        channel.settimeout(0.0) # Non-blocking

        # 4. Bridge WebSocket and SSH Channel
        while True:
            # Use select for efficient I/O multiplexing
            # Wait for reading from websocket (ws.fileno isn't standard, check Sock impl if needed),
            # reading from SSH channel, or error
            # A simpler (but potentially less efficient) approach without select:
            try:
                # Read from SSH -> Send to WS
                if channel.recv_ready():
                    ssh_data = channel.recv(BUFFER_SIZE)
                    if not ssh_data: # Channel closed
                        logging.info("SSH channel closed by remote end.")
                        break
                    ws.send(ssh_data.decode('utf-8', errors='replace')) # Send raw bytes if xterm.js handles binary

                # Read from WS -> Send to SSH
                # Use receive with timeout to prevent blocking indefinitely
                ws_data_str = ws.receive(timeout=0.01) # Small timeout
                if ws_data_str:
                    try:
                        ws_data = json.loads(ws_data_str)
                        if ws_data.get('type') == 'input':
                            channel.send(ws_data['data'])
                        elif ws_data.get('type') == 'resize':
                             cols = ws_data.get('cols', 80)
                             rows = ws_data.get('rows', 24)
                             channel.resize_pty(width=cols, height=rows)
                             logging.debug(f"Resized PTY to {cols}x{rows}")
                    except json.JSONDecodeError:
                         logging.warning(f"Received non-JSON data on WebSocket: {ws_data_str[:50]}...")
                    except Exception as e:
                        logging.error(f"Error processing WebSocket message: {e}")


                if not channel.active:
                    logging.info("SSH channel became inactive.")
                    break

            except TimeoutError: # From ws.receive(timeout=...)
                 continue # No data received, loop again
            except Exception as e:
                logging.error(f"Error during SSH/WS bridge: {e}", exc_info=True)
                ws.send(json.dumps({"type": "error", "data": f"Runtime Error: {e}"}))
                break

    except Exception as e:
        logging.error(f"Unexpected error in ssh_interaction: {e}", exc_info=True)
        try:
            # Try sending error to client if WS is still available
             ws.send(json.dumps({"type": "error", "data": f"Internal Server Error: {e}"}))
        except Exception:
            pass # Ignore if we can't even send the error
    finally:
        logging.info("Closing SSH connection and channel.")
        if channel:
            channel.close()
        if ssh:
            ssh.close()
        # The WebSocket closing is handled by the main @sock.route handler

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main terminal page."""
    return render_template('terminal.html')

@app.route('/config', methods=['GET', 'POST'])
def configure():
    """Handles viewing and saving the configuration."""
    message = None
    if request.method == 'POST':
        config_data = {
            'hostname': request.form.get('hostname', '').strip(),
            'port': int(request.form.get('port', 22)),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '') # Store password directly (INSECURE)
        }
        if save_config(config_data):
            message = "Configuration saved successfully!"
        else:
            message = "Error saving configuration!"
        # Load again to show updated values in the form
        current_config = load_config()
        return render_template('config.html', config=current_config, message=message)
    else:
        current_config = load_config()
        return render_template('config.html', config=current_config)


@sock.route('/ws')
def websocket_route(ws):
    """Handles WebSocket connections for the terminal."""
    logging.info("WebSocket connection received.")
    config = load_config()

    # Run SSH interaction in a separate thread to avoid blocking Flask-Sock
    # ssh_thread = threading.Thread(target=ssh_interaction, args=(ws, config))
    # ssh_thread.start()
    # ssh_thread.join() # Wait for the thread to finish

    # Direct call (simpler for this demo, assumes Flask-Sock handles concurrency well enough or uses gevent/eventlet)
    ssh_interaction(ws, config)

    logging.info("WebSocket connection closed.")


# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Flask server for WebSSH Auto Demo...")
    print("WARNING: THIS DEMO STORES PASSWORDS INSECURELY IN config.json.")
    print("Access configuration at http://127.0.0.1:5000/config")
    print("Access terminal (auto-connects) at http://127.0.0.1:5000/")
    # Use host='0.0.0.0' to make accessible on your network (use with caution!)
    app.run(host='127.0.0.1', port=5000, debug=True) # debug=True enables auto-reloading