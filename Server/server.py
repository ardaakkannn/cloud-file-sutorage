import os
import socket
import threading
from tkinter import Tk, Label, Button, Entry, Listbox, filedialog, END
import json


class ServerApp:
    def __init__(self):
        self.server_socket = None
        self.clients = {}
        self.files = {}
        self.save_directory = self.get_default_save_directory()
        os.makedirs(self.save_directory, exist_ok=True)

        self.init_gui()

    # this function is for creating a GUI

    def get_default_save_directory(self):
        """Create a default save directory in the user's home folder"""
        return os.path.join(os.path.expanduser("~"), "FileShareServer")

    def init_gui(self):

        self.root = Tk()
        self.root.title("Server")

        Label(self.root, text="Port:").grid(row=0, column=0)
        self.port_entry = Entry(self.root)
        self.port_entry.grid(row=0, column=1)

        Button(self.root, text="Set Save Directory", command=self.set_save_directory).grid(
            row=1, column=0, columnspan=2)
        Button(self.root, text="Start Server", command=self.start_server).grid(
            row=2, column=0, columnspan=2)

        self.log_box = Listbox(self.root, width=50, height=15)
        self.log_box.grid(row=3, column=0, columnspan=2)

        # delete window protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
        # json folder name for saving file
        self.file_metadata_path = "file_metadata.json"
        self.load_files()  # load priviusly added files

    def load_files(self):
        """Enhanced file loading with robust error handling"""
        try:
            if os.path.exists(self.file_metadata_path):
                with open(self.file_metadata_path, "r") as f:
                    loaded_files = json.load(f)

                # Validate that files still exist in the directory
                validated_files = {}
                for filename, owner in loaded_files.items():
                    file_path = os.path.join(self.save_directory, filename)
                    if os.path.exists(file_path):
                        validated_files[filename] = owner

                self.files = validated_files
                self.log(
                    f"Loaded {len(self.files)} files from previous session.")
            else:
                self.log("No previous file metadata found, starting fresh.")
        except (json.JSONDecodeError, IOError):
            self.log("Error loading file metadata. Starting with empty file list.")
            self.files = {}

    def save_files(self):
        """saving folder list into json file"""
        with open(self.file_metadata_path, "w") as f:
            json.dump(self.files, f)
        self.log("File metadata saved.")

    def set_save_directory(self):
        # select a directory for downlading files
        self.save_directory = filedialog.askdirectory()
        if self.save_directory:
            self.log("Save directory set to: " + self.save_directory)

    def start_server(self):
        port = int(self.port_entry.get())
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server_socket.bind(("", port))  # binding server to the port
        self.server_socket.listen(5)

        self.log(f"Server started on port {port}")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(
                client_socket,), daemon=True).start()

    def handle_client(self, client_socket):
        # get the client name
        client_name = client_socket.recv(1024).decode()
        if client_name in self.clients:
            # if it is already in use:
            client_socket.send("ERROR: Name already in use.".encode())
            client_socket.close()
            return

        # if it is not used before:
        self.clients[client_name] = client_socket
        self.log(f"{client_name} connected.")

        # connection established
        client_socket.send(f"CONNECTED|{client_name}".encode())

        # loop for client messages
        while True:
            try:
                message = client_socket.recv(1024).decode()
                if not message:
                    break
                if message.startswith("DISCONNECT"):
                    # if disconnect request is received
                    self.log(f"{client_name} requested disconnection.")
                    break
                self.process_command(client_name, message, client_socket)
            except ConnectionResetError:
                break

        # finish the connection
        self.log(f"{client_name} disconnected.")
        del self.clients[client_name]
        client_socket.close()

    def process_command(self, client_name, message, client_socket):
        command, *args = message.split("|")

        if command == "UPLOAD":
            filename, file_content = args
            self.upload_file(client_name, filename,
                             file_content, client_socket)
        elif command == "LIST":
            self.send_file_list(client_socket)
        elif command == "DELETE":
            filename = args[0]
            self.delete_file(client_name, filename, client_socket)
        elif command == "DOWNLOAD":
            filename, owner = args
            self.send_file(client_name, filename, owner, client_socket)
        else:
            client_socket.send("ERROR: Invalid command.".encode())

    def upload_file(self, client_name, filename, file_content, client_socket):
        # Ensure save directory exists
        os.makedirs(self.save_directory, exist_ok=True)

        # Create unique filename with client name
        unique_filename = f"{client_name}_{filename}"
        file_path = os.path.join(self.save_directory, unique_filename)

        # Write file with full path
        with open(file_path, "w") as f:
            f.write(file_content)

        # Update files dictionary and save metadata
        self.files[unique_filename] = client_name
        self.log(f"{client_name} uploaded {filename}")
        client_socket.send(f"File {filename} uploaded successfully.".encode())

        # Always save files after upload
        self.save_files()

    # file check function

    def send_file_list(self, client_socket):
        if not self.files:
            client_socket.send("No files available.".encode())
        else:
            file_list = "\n".join(
                [f"{fname} (Owner: {owner})" for fname, owner in self.files.items()])
            client_socket.send(file_list.encode())

    def delete_file(self, client_name, filename, client_socket):
        unique_filename = f"{client_name}_{filename}"
        if unique_filename not in self.files:
            client_socket.send(
                "ERROR: File not found or not owned by you.".encode())
            return

        os.remove(os.path.join(self.save_directory, unique_filename))
        del self.files[unique_filename]
        self.log(f"{client_name} deleted {filename}")
        client_socket.send(f"File {filename} deleted successfully.".encode())
        self.save_files()  # updating folder

    def send_file(self, client_name, filename, owner, client_socket):
        unique_filename = f"{owner}_{filename}"
        if unique_filename not in self.files:
            client_socket.send("ERROR: File not found.".encode())
            return

        file_path = os.path.join(self.save_directory, unique_filename)
        with open(file_path, "r") as f:
            file_content = f.read()

        # notify the owner of the file
        client_socket.send(f"FILE_CONTENT|{filename}|{file_content}".encode())

        self.log(f"{client_name} downloaded {filename} from {owner}")

        if owner in self.clients:
            owner_socket = self.clients[owner]
            notification = f"{client_name} downloaded your file: {filename}"
            owner_socket.send(notification.encode())

    def log(self, message):
        self.log_box.insert(END, message)
        self.log_box.yview(END)

    def set_save_directory(self):
        # Allow user to change save directory
        new_directory = filedialog.askdirectory()
        if new_directory:
            # Move existing files to new directory
            self.move_files_to_new_directory(new_directory)

            # Update save directory and metadata path
            self.save_directory = new_directory
            self.file_metadata_path = os.path.join(
                self.save_directory, "file_metadata.json")

            # Reload files and save updated metadata
            self.load_files()
            self.save_files()

            self.log(f"Save directory changed to: {self.save_directory}")

    def move_files_to_new_directory(self, new_directory):
        """Move existing files to new directory"""
        os.makedirs(new_directory, exist_ok=True)

        for filename in list(self.files.keys()):
            old_path = os.path.join(self.save_directory, filename)
            new_path = os.path.join(new_directory, filename)

            try:
                # Move file to new directory
                os.rename(old_path, new_path)
            except FileNotFoundError:
                # Remove from files if original file doesn't exist
                del self.files[filename]
                self.log(f"File {filename} not found, removing from metadata.")

    def on_close(self):
        if self.server_socket:
            self.server_socket.close()
        self.save_files()  # saving folder
        self.root.destroy()


if __name__ == "__main__":
    ServerApp()
