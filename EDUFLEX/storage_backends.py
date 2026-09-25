import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

# django-cloudinary-storage configura el SDK de Cloudinary para sus propias
# storage classes, pero acá llamamos a cloudinary.uploader directamente
# (para poder subir como 'authenticated'), así que hay que asegurarnos de
# que el SDK tenga las credenciales cargadas también para estas llamadas.
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE.get('CLOUD_NAME'),
    api_key=settings.CLOUDINARY_STORAGE.get('API_KEY'),
    api_secret=settings.CLOUDINARY_STORAGE.get('API_SECRET'),
)


@deconstructible
class CapturaPrivadaStorage(Storage):
    """Fotos de niños capturadas durante la detección (somnolencia/distracción).

    Se suben a Cloudinary como recurso 'authenticated' (privado: no se puede
    acceder por URL directa) y la URL se firma al vuelo cada vez que se pide
    (ver .url()), para que un profesor la vea desde el reporte sin que
    el link quede público ni indexable.
    """
    RESOURCE_TYPE = 'image'
    DELIVERY_TYPE = 'authenticated'

    def _save(self, name, content):
        public_id = name.rsplit('.', 1)[0]
        resultado = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            resource_type=self.RESOURCE_TYPE,
            type=self.DELIVERY_TYPE,
            overwrite=False,
        )
        return resultado['public_id']

    def exists(self, name):
        # Los nombres ya incluyen niño/reporte/timestamp con microsegundos:
        # siempre son únicos, así que no hace falta ir a preguntarle a Cloudinary.
        return False

    def url(self, name):
        url, _opciones = cloudinary.utils.cloudinary_url(
            name,
            resource_type=self.RESOURCE_TYPE,
            type=self.DELIVERY_TYPE,
            sign_url=True,
        )
        return url

    def size(self, name):
        raise NotImplementedError("CapturaPrivadaStorage no lee archivos, solo sube y firma URLs.")

    def open(self, name, mode='rb'):
        raise NotImplementedError("CapturaPrivadaStorage no lee archivos, solo sube y firma URLs.")

    def delete(self, name):
        cloudinary.uploader.destroy(name, resource_type=self.RESOURCE_TYPE, type=self.DELIVERY_TYPE)
