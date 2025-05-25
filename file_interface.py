import os
import base64
import json

class FileInterface:
    def __init__(self, base_folder='files'):
        self.base_folder = base_folder
        os.makedirs(self.base_folder, exist_ok=True)

    def list(self, params):
        """List semua file dalam folder base_folder"""
        try:
            files = os.listdir(self.base_folder)
            return dict(status='OK', data=files)
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def get(self, params):
        """Download file: params[0] = filename"""
        if not params:
            return dict(status='ERROR', data='Nama file tidak diberikan')
        filename = params[0]
        path = os.path.join(self.base_folder, filename)
        if not os.path.isfile(path):
            return dict(status='ERROR', data='File tidak ditemukan')
        try:
            with open(path, 'rb') as f:
                data_b64 = base64.b64encode(f.read()).decode()
            return dict(status='OK', data_file=data_b64)
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def upload(self, params):
        """Upload file: params[0] = filename, params[1] = base64 content"""
        if len(params) < 2:
            return dict(status='ERROR', data='Parameter kurang untuk upload')
        filename = params[0]
        data_b64 = params[1]
        path = os.path.join(self.base_folder, filename)
        try:
            data = base64.b64decode(data_b64)
            with open(path, 'wb') as f:
                f.write(data)
            return dict(status='OK', data='Upload sukses')
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def delete(self, params):
        """Hapus file: params[0] = filename"""
        if not params:
            return dict(status='ERROR', data='Nama file tidak diberikan')
        filename = params[0]
        path = os.path.join(self.base_folder, filename)
        if not os.path.isfile(path):
            return dict(status='ERROR', data='File tidak ditemukan')
        try:
            os.remove(path)
            return dict(status='OK', data='File dihapus')
        except Exception as e:
            return dict(status='ERROR', data=str(e))
