import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import time

BROADCAST_PORT = 50000
FILE_TRANSFER_PORT = 5001
DISCOVERY_INTERVAL = 5  # seconds
BUFFER_SIZE = 8192

class ServerlessP2PApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Yamin Peer - P2P File Sharing")
        self.root.geometry("600x400")
        self.root.configure(bg="#1e1e2f")
        self.peers = {}  # {ip: last_seen_time}
        self.files_to_send = []  # list of (file_path, relative_path)

        self.build_gui()

        threading.Thread(target=self.start_udp_broadcast_listener, daemon=True).start()
        threading.Thread(target=self.start_udp_broadcaster, daemon=True).start()
        threading.Thread(target=self.start_file_receiver, daemon=True).start()

    def build_gui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=10, relief="flat", background="#4f46e5", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[('active', '#6366f1')])
        style.configure("TLabel", background="#1e1e2f", foreground="white", font=("Segoe UI", 10))

        ttk.Label(self.root, text="Discovered Peers:", font=("Segoe UI", 12, "bold"), foreground="#60a5fa").pack(pady=10)

        self.peer_listbox = tk.Listbox(self.root, width=50, height=6, font=("Segoe UI", 10), bg="#2e2e3e", fg="white", selectbackground="#4f46e5")
        self.peer_listbox.pack(pady=5)

        button_frame = tk.Frame(self.root, bg="#1e1e2f")
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Refresh Peers", command=self.refresh_peers).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(button_frame, text="Select Files", command=self.select_files).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(button_frame, text="Select Folder", command=self.select_folder).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(button_frame, text="Send File(s)", command=self.send_file_to_selected_peer).grid(row=0, column=3, padx=5, pady=5)

        self.file_label = ttk.Label(self.root, text="No files selected", wraplength=500, font=("Segoe UI", 10, "italic"), foreground="#a1a1aa")
        self.file_label.pack(pady=10)

        self.status_label = ttk.Label(self.root, text="Running...", font=("Segoe UI", 9, "italic"), foreground="#cbd5e1")
        self.status_label.pack(pady=5)

    def start_file_receiver(self):
        server = socket.socket()
        server.bind(('', FILE_TRANSFER_PORT))
        server.listen(5)
        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_incoming_file, args=(conn, addr), daemon=True).start()

    def handle_incoming_file(self, conn, addr):
        try:
            rel_path = conn.recv(BUFFER_SIZE).decode().strip()
            conn.send(b"OK")
            save_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'yamin peer')
            full_path = os.path.join(save_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                while True:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    f.write(data)
            conn.close()
            self.status_label.config(text=f"Received: {rel_path}")
        except Exception as e:
            print("Receive error:", e)

    def send_file_to_selected_peer(self):
        selection = self.peer_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Peer Selected", "Please select a peer to send the files to.")
            return
        if not self.files_to_send:
            messagebox.showwarning("No Files", "Please select file(s) or folder(s) to send.")
            return
        ip = self.peer_listbox.get(selection[0])
        threading.Thread(target=self.send_files, args=(ip,), daemon=True).start()

    def send_files(self, ip):
        try:
            for file_path, rel_path in self.files_to_send:
                s = socket.socket()
                s.connect((ip, FILE_TRANSFER_PORT))
                s.send(rel_path.encode())
                ack = s.recv(BUFFER_SIZE)
                with open(file_path, 'rb') as f:
                    while True:
                        bytes_read = f.read(BUFFER_SIZE)
                        if not bytes_read:
                            break
                        s.sendall(bytes_read)
                s.close()
            messagebox.showinfo("Success", f"{len(self.files_to_send)} file(s) sent to {ip}")
        except Exception as e:
            messagebox.showerror("Send Error", str(e))

    def start_udp_broadcaster(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        while True:
            message = f"p2p:{local_ip}"
            sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
            time.sleep(DISCOVERY_INTERVAL)

    def start_udp_broadcast_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', BROADCAST_PORT))
        while True:
            data, addr = sock.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("p2p:"):
                peer_ip = msg.split(":")[1]
                if peer_ip != self.get_my_ip():
                    self.peers[peer_ip] = time.time()
                    self.update_peer_listbox()

    def get_my_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def update_peer_listbox(self):
        self.peer_listbox.delete(0, tk.END)
        now = time.time()
        for ip, last_seen in self.peers.items():
            if now - last_seen < DISCOVERY_INTERVAL * 2:
                self.peer_listbox.insert(tk.END, ip)

    def refresh_peers(self):
        self.update_peer_listbox()

    def select_files(self):
        paths = filedialog.askopenfilenames()
        if paths:
            self.files_to_send = [(p, os.path.basename(p)) for p in paths]
            filenames = [os.path.basename(p) for p in paths]
            self.file_label.config(text=", ".join(filenames))

    def select_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            file_list = []
            folder_name = os.path.basename(folder_path)
            for filename in os.listdir(folder_path):
                full_path = os.path.join(folder_path, filename)
                if os.path.isfile(full_path):
                    rel_path = os.path.join(folder_name, filename)
                    file_list.append((full_path, rel_path))
            if file_list:
                self.files_to_send = file_list
                self.file_label.config(text=f"Folder: {folder_name} ({len(file_list)} files)")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerlessP2PApp(root)
    root.mainloop()
