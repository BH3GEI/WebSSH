# WebSSH Demo

A demonstration of a web-based SSH client. This application offers a terminal in your browser to connect to an SSH server.

## Overview

*   Browser-based terminal for SSH access.
*   Configuration page for SSH connection details (hostname, port, username, password).
*   Uses WebSockets for real-time communication.

## Technologies Used

*   **Backend:** Python, Flask
*   **WebSocket:** Flask-Sock
*   **SSH Connection:** Paramiko
*   **Frontend:** HTML, JavaScript (implicitly, via xterm.js likely used in `terminal.html`)

## Prerequisites

*   Python 3.x
*   pip (Python package installer)

## Setup and Installation

1.  **Clone the repository (if applicable) or download the files.**

2.  **Navigate to the project directory:**
    ```bash
    cd path/to/WebSSH
    ```

3.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

4.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  Run the application first (see next section).
2.  Open your web browser and navigate to `http://127.0.0.1:5000/config`.
3.  Enter the SSH server details:
    *   **Hostname:** The IP address or hostname of your SSH server.
    *   **Port:** The SSH port (default is 22).
    *   **Username:** Your SSH username.
    *   **Password:** Your SSH password.
4.  Click "Save Configuration". The configuration will be saved to `config.json` in the project directory.

**Security Warning:** This demo application stores the SSH password in plain text in the `config.json` file. This is **highly insecure** and should **NOT** be used in a production environment or with sensitive credentials. For production use, consider implementing more secure methods like SSH key-based authentication and storing secrets securely.

## Running the Application

1.  Ensure you have completed the setup and configuration steps.
2.  Run the Flask application:
    ```bash
    python app.py
    ```
3.  The application will start, and you should see output similar to this:
    ```
    Starting Flask server for WebSSH Auto Demo...
    WARNING: THIS DEMO STORES PASSWORDS INSECURELY IN config.json.
    Access configuration at http://127.0.0.1:5000/config
    Access terminal (auto-connects) at http://127.0.0.1:5000/
    ```
4.  Open your web browser and navigate to `http://127.0.0.1:5000/` to access the web terminal. It will attempt to automatically connect using the saved configuration.

## How it Works

*   The Flask application serves the HTML pages (`terminal.html` and `config.html`).
*   When you access the terminal page, JavaScript in the browser establishes a WebSocket connection to the `/ws` endpoint on the server.
*   The `ssh_interaction` function in `app.py` handles the WebSocket connection. It reads the SSH configuration from `config.json` and uses Paramiko to establish an SSH connection to the specified server.
*   Data is then relayed between the web browser (via WebSockets) and the SSH server (via Paramiko). User input from the browser is sent to the SSH server, and output from the SSH server is sent back to the browser to be displayed in the terminal.

