import subprocess
import time
import os
import csv
import argparse
import concurrent.futures

from file_client_cli import run_stress_test

# Server script names
SERVER_THREAD_SCRIPT  = 'file_server_thread.py'
SERVER_PROCESS_SCRIPT = 'file_server_process.py'

# Default parameters
CLIENT_WORKERS = [1, 5, 50]
SERVER_WORKERS = [1, 5, 50]
OPERATIONS     = ['upload', 'download']

CSV_FILE   = 'stress_test_results.csv'
FIELDNAMES = [
    'Nomor', 'mode', 'operation', 'volume_mb', 'client_workers', 'server_workers',
    'success_client_workers', 'fail_client_workers',
    'avg_duration_per_client_sec', 'avg_throughput_per_client_bps',
    'success_server_workers', 'fail_server_workers'
]

def parse_args():
    p = argparse.ArgumentParser(description='Orkestrasi Stress Test')
    p.add_argument('--start-port', type=int, default=6666,
                   help='Port awal untuk server thread (thread), process akan +1')
    p.add_argument('--mode',      type=str,
                   help='Comma-separated list: thread,process')
    p.add_argument('--workers',   type=str,
                   help='Comma-separated list of server worker pool sizes (e.g. 1,5,50)')
    p.add_argument('--volumes',   type=str,
                   help='Comma-separated list of file volumes in MB (e.g. 10,50,100)')
    return p.parse_args()

def load_completed_scenarios(filename):
    completed = set()
    if os.path.exists(filename):
        with open(filename, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (
                    row['mode'],
                    row['operation'],
                    row['volume_mb'],
                    row['client_workers'],
                    row['server_workers']
                )
                completed.add(key)
    return completed

def append_result_to_csv(filename, fieldnames, result, nomor):
    file_exists = os.path.exists(filename)
    with open(filename, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        row = {
            'Nomor': nomor,
            'mode': result['mode'],
            'operation': result['operation'],
            'volume_mb': result['volume_mb'],
            'client_workers': result['client_workers'],
            'server_workers': result['server_workers'],
            'success_client_workers': result['success_client_workers'],
            'fail_client_workers': result['fail_client_workers'],
            'avg_duration_per_client_sec': result['avg_duration_per_client_sec'],
            'avg_throughput_per_client_bps': result['avg_throughput_per_client_bps'],
            'success_server_workers': result['success_server_workers'],
            'fail_server_workers': result['fail_server_workers']
        }
        print(f"DEBUG: Writing to CSV Nomor {nomor}: {row}")
        writer.writerow(row)

def print_scenario_result(res, nomor):
    print("\n" + "="*60)
    print(f"Nomor           : {nomor}")
    print(f"Operasi         : {res['operation']}")
    print(f"Volume file (MB): {res['volume_mb']}")
    print(f"Client Workers  : {res['client_workers']}")
    print(f"Server Workers  : {res['server_workers']}")
    print(f"Mode            : {'Threading' if res.get('mode','thread')=='thread' else 'Processing'}")
    print(f"Waktu Total (s) : {res['avg_duration_per_client_sec']:.2f}")
    print(f"Throughput (B/s): {res['avg_throughput_per_client_bps']:.2f}")
    print(f"Client Sukses   : {res['success_client_workers']}")
    print(f"Client Gagal    : {res['fail_client_workers']}")
    print(f"Server Sukses   : {res['success_server_workers']}")
    print(f"Server Gagal    : {res['fail_server_workers']}")
    print("="*60 + "\n")

def start_server(script, worker_pool, port):
    """Launch server subprocess, return Popen handle."""
    proc = subprocess.Popen(
        ['python', script, str(worker_pool), str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)  # allow server to initialize
    return proc

def stop_server(proc):
    """Terminate server subprocess."""
    proc.terminate()
    proc.wait()

def run_tests_with_server(script_name, server_worker, mode_name, port,
                          completed, start_nomor, volumes, timeout_sec=180):
    """
    Run stress-test scenarios on a single server instance.
    Applies a timeout per scenario; if exceeded, marks scenario as failed.
    """
    proc = start_server(script_name, server_worker, port)
    nomor = start_nomor
    try:
        for volume in volumes:
            for operation in OPERATIONS:
                for client_worker in CLIENT_WORKERS:
                    nomor += 1
                    key = (mode_name, operation, str(volume),
                           str(client_worker), str(server_worker))
                    if key in completed:
                        print(f"Skip already completed: {key}")
                        continue

                    print(f"Running {mode_name.upper()} | op={operation} | vol={volume}MB | "
                          f"client={client_worker} | server={server_worker} (timeout={timeout_sec}s)")

                    # execute run_stress_test with timeout
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            run_stress_test,
                            operation, volume, client_worker, server_worker,
                            concurrency_mode=mode_name, port=port
                        )
                        try:
                            res = future.result(timeout=timeout_sec)
                        except concurrent.futures.TimeoutError:
                            print(f"⚠️ Timeout after {timeout_sec}s – marking scenario as FAILED")
                            res = {
                                'mode': mode_name,
                                'operation': operation,
                                'volume_mb': volume,
                                'client_workers': client_worker,
                                'server_workers': server_worker,
                                'success_client_workers': 0,
                                'fail_client_workers': client_worker,
                                'avg_duration_per_client_sec': float(timeout_sec),
                                'avg_throughput_per_client_bps': 0.0,
                                'success_server_workers': 0,
                                'fail_server_workers': server_worker
                            }

                    # ensure mode is set
                    res.setdefault('mode', mode_name)

                    print_scenario_result(res, nomor)
                    append_result_to_csv(CSV_FILE, FIELDNAMES, res, nomor)
                    completed.add(key)
    finally:
        stop_server(proc)
    return nomor

def main():
    args = parse_args()

    # Determine modes to run
    modes = args.mode.split(',') if args.mode else ['thread', 'process']
    # Determine server worker counts
    if args.workers:
        workers = [int(x) for x in args.workers.split(',')]
    else:
        workers = SERVER_WORKERS
    # Determine volume order (10,50 first; 100 last)
    if args.volumes:
        vols_in = [int(x) for x in args.volumes.split(',')]
        volumes = [v for v in vols_in if v != 100]
        if 100 in vols_in:
            volumes.append(100)
    else:
        volumes = [10, 50, 100]

    completed = load_completed_scenarios(CSV_FILE)
    nomor = 1 + len(completed)

    # Run for each mode and server worker setting
    for mode, script, port in [
        ('thread',  SERVER_THREAD_SCRIPT,  6666),
        ('process', SERVER_PROCESS_SCRIPT, 6667)
    ]:
        if mode not in modes:
            continue
        for server_worker in workers:
            nomor = run_tests_with_server(
                script, server_worker, mode, port,
                completed, nomor, volumes, timeout_sec=180
            )

if __name__ == '__main__':
    main()
