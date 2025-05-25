import json
import logging
import shlex

from file_interface import FileInterface

class FileProtocol:
    def __init__(self, server_ref=None):
        self.file = FileInterface()
        self.server_ref = server_ref  # referensi server untuk akses statistik

    def proses_string(self, string_datamasuk=''):
        logging.warning(f"string diproses: {string_datamasuk}")

        # Tangani command STATUS khusus untuk statistik server
        if string_datamasuk.strip().upper() == 'STATUS':
            if self.server_ref:
                sukses, gagal = self.server_ref.get_worker_stats()
                return json.dumps(dict(status='OK', data={
                    'worker_sukses': sukses,
                    'worker_gagal': gagal
                }))
            else:
                return json.dumps(dict(status='ERROR', data='server stats tidak tersedia'))

        # Proses command upload khusus karena base64 bisa ada spasi
        if string_datamasuk.upper().startswith('UPLOAD '):
            parts = string_datamasuk.split(' ', 2)
            if len(parts) < 3:
                return json.dumps(dict(status='ERROR', data='parameter upload kurang'))
            c_request = parts[0].lower()
            nama_file = parts[1]
            isi_file = parts[2]
            params = [nama_file, isi_file]
        else:
            tokens = shlex.split(string_datamasuk)
            if not tokens:
                return json.dumps(dict(status='ERROR', data='request kosong'))
            c_request = tokens[0].lower()
            params = tokens[1:]

        logging.warning(f"memproses request: {c_request}")

        try:
            handler = getattr(self.file, c_request)
            return json.dumps(handler(params))
        except AttributeError:
            return json.dumps(dict(status='ERROR', data='request tidak dikenali'))

if __name__ == '__main__':
    fp = FileProtocol()
    print(fp.proses_string("LIST"))
    print(fp.proses_string("GET pokijan.jpg"))
    dummy_b64 = "cHJvZ2phciBrZWxhc...=="
    print(fp.proses_string(f"UPLOAD progjar_kelas_c.txt {dummy_b64}"))
