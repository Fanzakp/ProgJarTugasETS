import socket
import json
import base64
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import csv

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 6666

def set_server_port(port):
    global SERVER_PORT
    SERVER_PORT = port

def send_command(cmd):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
    sock.connect((SERVER_HOST, SERVER_PORT))
    try:
        full_msg = cmd + "\r\n\r\n"
        sock.sendall(full_msg.encode())
        buffer = b''
        while True:
            chunk = sock.recv(256 * 1024)  # buffer besar
            if not chunk:
                break
            buffer += chunk
            if b'\r\n\r\n' in buffer:
                break
        response_str = buffer.decode()
        response_str = response_str.replace('\r\n\r\n', '')
        return json.loads(response_str)
    finally:
        sock.close()

def generate_dummy_file(filename, size_mb):
    size_bytes = size_mb * 1024 * 1024
    with open(filename, 'wb') as f:
        f.write(os.urandom(size_bytes))

def upload_file(filepath):
    if not os.path.isfile(filepath):
        return False, "File tidak ditemukan"
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as fp:
        b64 = base64.b64encode(fp.read()).decode()
    res = send_command(f'UPLOAD {filename} {b64}')
    if res['status'] == 'OK':
        return True, res['data']
    else:
        return False, res['data']

def download_file(filename, dest_folder):
    res = send_command(f'GET {filename}')
    if res['status'] == 'OK':
        data = base64.b64decode(res['data_file'])
        path = os.path.join(dest_folder, filename)
        with open(path, 'wb') as fp:
            fp.write(data)
        return True, f"File '{filename}' berhasil di-download"
    else:
        return False, res['data']

def stress_upload_worker(file_size_mb):
    filename = f'dummy_{file_size_mb}MB.dat'
    generate_dummy_file(filename, file_size_mb)
    start = time.time()
    success, msg = upload_file(filename)
    end = time.time()
    duration = end - start
    size_bytes = file_size_mb * 1024 * 1024
    try:
        os.remove(filename)
    except:
        pass
    print(f"[Worker Upload] File: {filename}, Success: {success}, Duration: {duration:.3f}s")
    return success, duration, size_bytes

def stress_download_worker(file_size_mb):
    filename = f'dummy_{file_size_mb}MB.dat'
    start = time.time()
    success, msg = download_file(filename, '.')
    end = time.time()
    duration = end - start
    size_bytes = file_size_mb * 1024 * 1024
    try:
        os.remove(filename)
    except:
        pass
    print(f"[Worker Download] File: {filename}, Success: {success}, Duration: {duration:.3f}s")
    return success, duration, size_bytes

def run_stress_test(operation, file_size_mb, client_workers, server_workers, concurrency_mode='thread', port=6666):
    set_server_port(port)
    print(f"Mulai stress test: {operation}, file {file_size_mb}MB, client workers {client_workers}, server workers {server_workers}, mode {concurrency_mode}, port {port}")

    ExecutorClass = ThreadPoolExecutor if concurrency_mode == 'thread' else ProcessPoolExecutor
    worker_func = stress_upload_worker if operation == 'upload' else stress_download_worker

    success_count = 0
    fail_count = 0
    durations = []

    with ExecutorClass(max_workers=client_workers) as executor:
        futures = [executor.submit(worker_func, file_size_mb) for _ in range(client_workers)]
        for future in as_completed(futures):
            try:
                success, duration, _ = future.result()
                if success:
                    success_count += 1
                    durations.append(duration)
                else:
                    fail_count += 1
            except Exception as e:
                print(f"Worker raised exception: {e}")
                fail_count += 1

    avg_duration = max(durations) if durations else 0
    total_bytes = success_count * file_size_mb * 1024 * 1024
    avg_throughput = total_bytes / avg_duration if avg_duration > 0 else 0

    server_status = send_command('STATUS')
    if server_status['status'] == 'OK':
        success_server_workers = server_status['data'].get('worker_sukses', 'unknown')
        fail_server_workers = server_status['data'].get('worker_gagal', 'unknown')
    else:
        success_server_workers = 'unknown'
        fail_server_workers = 'unknown'

    result = {
        'operation': operation,
        'volume_mb': file_size_mb,
        'client_workers': client_workers,
        'server_workers': server_workers,
        'success_client_workers': success_count,
        'fail_client_workers': fail_count,
        'avg_duration_per_client_sec': avg_duration,
        'avg_throughput_per_client_bps': avg_throughput,
        'success_server_workers': success_server_workers,
        'fail_server_workers': fail_server_workers,
    }
    print(f"[Stress Test Result] {result}")
    return result
