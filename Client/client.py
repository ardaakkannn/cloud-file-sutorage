import socket
import threading
from tkinter import Tk, Label, Button, Entry, Listbox, filedialog, END


class ClientApp:
    def __init__(self):
        self.client_socket = None
        self.server_ip = ""
        self.server_port = 0
        self.username = ""

        self.init_gui()

    # initalizing the graphical user interface

    def init_gui(self):
        self.root = Tk()
        self.root.title("Client")

        Label(self.root, text="Server IP:").grid(row=0, column=0)
        self.server_ip_entry = Entry(self.root)
        self.server_ip_entry.grid(row=0, column=1)

        Label(self.root, text="Port:").grid(row=1, column=0)
        self.server_port_entry = Entry(self.root)
        self.server_port_entry.grid(row=1, column=1)

        Label(self.root, text="Username:").grid(row=2, column=0)
        self.username_entry = Entry(self.root)
        self.username_entry.grid(row=2, column=1)

        Button(self.root, text="Connect", command=self.connect_to_server).grid(
            row=3, column=0, columnspan=2)
        Button(self.root, text="Disconnect", command=self.disconnect).grid(
            row=4, column=0, columnspan=2)
        Button(self.root, text="Upload File", command=self.upload_file).grid(
            row=5, column=0, columnspan=2)
        Button(self.root, text="List Files", command=self.list_files).grid(
            row=6, column=0, columnspan=2)
        Button(self.root, text="Download File", command=self.download_file).grid(
            row=7, column=0, columnspan=2)
        Button(self.root, text="Delete File", command=self.delete_file).grid(
            row=8, column=0, columnspan=2)

        self.log_box = Listbox(self.root, width=50, height=10)
        self.log_box.grid(row=9, column=0, columnspan=2)

        # delete window protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    # establishing the connection for server side
    def connect_to_server(self):
        self.server_ip = self.server_ip_entry.get()
        self.server_port = int(self.server_port_entry.get())
        self.username = self.username_entry.get()

        def connect():
            try:
                # connect to server
                self.client_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.server_ip, self.server_port))

                # send the client name
                self.client_socket.send(self.username.encode())

                # wait for the response from connection
                response = self.client_socket.recv(1024).decode()
                if response.startswith("ERROR"):
                    self.log(response)
                    self.client_socket.close()
                    self.client_socket = None
                elif response.startswith("CONNECTED"):
                    self.log(f"Connected to server as {self.username}")
                    # in order to listen the connection-> threading
                    threading.Thread(
                        target=self.receive_messages, daemon=True).start()

            except Exception as e:
                self.log(f"Connection error: {e}")

           # new thread for connection
        threading.Thread(target=connect, daemon=True).start()

    def upload_file(self):
        if not self.client_socket:
            self.log("Not connected to server.")
            return

        # for text files
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt")])
        if not file_path:
            return

        filename = file_path.split("/")[-1]
        with open(file_path, "r") as file:
            file_content = file.read()

        command = f"UPLOAD|{filename}|{file_content}"
        self.client_socket.send(command.encode())
        self.log(f"Uploading {filename}...")

    # disconnect function
    def disconnect(self):
        if not self.client_socket:
            self.log("Not connected to server.")
            return
        try:
            self.client_socket.send("DISCONNECT|".encode())
            self.log("Disconnected from server.")
        except Exception as e:
            self.log(f"Error during disconnection: {e}")
        finally:
            self.client_socket.close()
            self.client_socket = None

    # list the files
    def list_files(self):
        if not self.client_socket:
            self.log("Not connected to server.")
            return

        try:
            # "LIST"
            self.client_socket.send("LIST|".encode())
            self.log("Requesting file list...")

            # log for upcoming response
            message = self.client_socket.recv(1024).decode()
            if message == "No files available.":
                self.log("No files available on the server.")
            else:
                self.log(f"File list:\n{message}")
                # throw exception if there is no file that we requested
        except Exception as e:
            self.log(f"Error requesting file list: {e}")

    def download_file(self):
        if not self.client_socket:
            self.log("Not connected to server.")
            return

        filename = self.get_user_input("Enter filename to download:")
        owner = self.get_user_input("Enter file owner:")

        if not filename or not owner:
            return

        # Kullanıcıdan dosyanın kaydedileceği dizini seçmesini iste
        save_directory = filedialog.askdirectory(
            title="Select Download Directory")
        if not save_directory:
            self.log("No directory selected. Download cancelled.")
            return

        # Kaydedilecek tam dosya yolu oluştur
        self.save_path = f"{save_directory}/{filename}"

        command = f"DOWNLOAD|{filename}|{owner}"
        self.client_socket.send(command.encode())
        self.log(f"Requesting download of {filename} from {owner}...")

    def delete_file(self):
        if not self.client_socket:
            self.log("Not connected to server.")
            return

        filename = self.get_user_input("Enter filename to delete:")

        if not filename:
            return

        command = f"DELETE|{filename}"
        self.client_socket.send(command.encode())
        # delete file
        self.log(f"Requesting deletion of {filename}...")

    def receive_messages(self):
        while True:
            try:
                # wait for the message from server
                message = self.client_socket.recv(1024).decode()

                if not message:  # if there is disconnection
                    self.log("Server disconnected.")
                    break

                # upcoming messages
                if message.startswith("FILE_CONTENT|"):
                    _, filename, file_content = message.split("|", 2)
                    # save the file into dedicated path
                    with open(self.save_path, "w") as file:
                        file.write(file_content)
                    self.log(
                        f"File '{filename}' downloaded and saved to '{self.save_path}'."
                    )
                elif message == "No files available.":  # no filers available
                    self.log("No files available on the server.")
                elif message.startswith("Connected to server"):  # connection message
                    if "Connected" not in self.log_box.get(0, END):
                        self.log(message)
                else:  # the other messages
                    self.log(message)

            except ConnectionResetError:
                self.log("Server connection reset.")
                break
            except Exception as e:
                # in order to avoid unnessecary exception
                if "Bad file descriptor" in str(e):
                    break
                else:
                    self.log(f"Error receiving message: {e}")
                    break

    def get_user_input(self, prompt):
        from tkinter.simpledialog import askstring
        return askstring("Input", prompt)

    def log(self, message):
        self.log_box.insert(END, message)
        self.log_box.yview(END)

    def on_close(self):
        if self.client_socket:
            self.client_socket.close()
        self.root.destroy()


if __name__ == "__main__":
    ClientApp()
