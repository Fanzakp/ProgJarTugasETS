import socket
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
from file_protocol import FileProtocol

class ServerThread:
    def __init__(self, ip='0.0.0.0', port=6666, worker_pool=5):
        self.ipinfo = (ip, port)
        self.worker_pool = worker_pool
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lock = threading.Lock()
        self.worker_results = []
        self.fp = FileProtocol(server_ref=self)

    def get_worker_stats(self):
        with self.lock:
            total = len(self.worker_results)
            sukses = sum(1 for r in self.worker_results if r)
            gagal = total - sukses
        return sukses, gagal

    def handle_client(self, conn, addr):
        buffer = b''
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b'\r\n\r\n' in buffer:
                    idx = buffer.index(b'\r\n\r\n')
                    raw_msg = buffer[:idx]
                    buffer = buffer[idx+4:]
                    data_str = raw_msg.decode()
                    logging.warning(f"string diproses: {data_str}")
                    if data_str.strip().upper() == 'STATUS':
                        hasil = self.fp.proses_string('STATUS')
                    else:
                        hasil = self.fp.proses_string(data_str)
                    hasil = hasil + "\r\n\r\n"
                    conn.sendall(hasil.encode())
            return True
        except Exception as e:
            logging.error(f"error saat proses client {addr}: {e}")
            return False
        finally:
            conn.close()

    def start(self):
        self.sock.bind(self.ipinfo)
        self.sock.listen(100)
        logging.warning(f"ServerThread berjalan di {self.ipinfo} dengan pool {self.worker_pool}")

        with ThreadPoolExecutor(max_workers=self.worker_pool) as executor:
            futures = set()
            while True:
                conn, addr = self.sock.accept()
                logging.warning(f"Connection dari {addr}")
                future = executor.submit(self.handle_client, conn, addr)
                futures.add(future)
                done = {f for f in futures if f.done()}
                for f in done:
                    try:
                        sukses = f.result()
                    except Exception:
                        sukses = False
                    with self.lock:
                        self.worker_results.append(sukses)
                    futures.remove(f)

def main():
    logging.basicConfig(level=logging.WARNING)
    worker_pool = 5
    if len(sys.argv) > 1:
        worker_pool = int(sys.argv[1])
    server = ServerThread(worker_pool=worker_pool)
    server.start()

if __name__ == '__main__':
    main()
