from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload


class LimiteTailleUpload(FileUploadHandler):
    """Interrompt la réception dès que la taille max est dépassée (avant écriture complète sur disque).
    À doubler d'une limite au reverse proxy en production (client_max_body_size)."""

    def new_file(self, *args, **kwargs):
        self.recu = 0
        return super().new_file(*args, **kwargs)

    def receive_data_chunk(self, raw_data, start):
        self.recu += len(raw_data)
        if self.recu > settings.SOLUGATION_UPLOAD_MAX_OCTETS:
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None
