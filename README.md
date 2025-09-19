# Prueba Backend ERP

Configuración base del servicio de documentos para la prueba técnica. Este repositorio incluye la infraestructura mínima para ejecutar la API de Django con PostgreSQL y Google Cloud Storage.

## Requisitos

- Docker y Docker Compose
- Cuenta de servicio de Google Cloud con permisos de lectura/escritura sobre el bucket configurado

## Variables de entorno

Copia el archivo `.env.example` a `.env` y ajusta los valores según tu entorno:

```bash
cp .env.example .env
```

### Credenciales de Google Cloud

Guarda el JSON de la cuenta de servicio dentro de `./secrets/gcp-service-account.json` (la carpeta `secrets/` está ignorada en Git). Asegúrate de que la ruta dentro del contenedor coincida con `GCP_CREDENTIALS_FILE`.

## Ejecución con Docker

```bash
docker compose up --build
```

El servicio web quedará disponible en `http://localhost:8000/` una vez que la base de datos esté lista. El contenedor ejecuta las migraciones automáticamente antes de iniciar el servidor (Gunicorn por defecto).

### Comandos útiles

- Ejecutar las migraciones manualmente:
  ```bash
  docker compose run --rm web python manage.py migrate
  ```
- Crear un superusuario:
  ```bash
  docker compose run --rm web python manage.py createsuperuser
  ```
- Cambiar a `runserver` (útil durante el desarrollo):
  ```bash
  USE_GUNICORN=0 docker compose up --build
  ```

## Desarrollo local sin Docker

1. Crear y activar un entorno virtual de Python 3.12.
2. Instalar dependencias:
   ```bash
   pip install -r api/requirements.txt
   ```
3. Exportar las variables de entorno del archivo `.env`.
4. Aplicar migraciones y levantar el servidor:
   ```bash
   python api/manage.py migrate
   python api/manage.py runserver
   ```

## Estructura relevante

- `api/`: código fuente del proyecto Django.
- `api/config/settings.py`: configuración de Django (PostgreSQL, GCS y REST Framework).
- `api/entrypoint.sh`: script que inicializa las migraciones y ejecuta el servidor.
- `docker-compose.yml`: orquestación de servicios web y base de datos.

## Uso de la API

### Flujo de carga de documentos

1. **Solicitar la URL firmada de carga.**
   Envía un `POST` a `http://localhost:8000/api/documents/` con un cuerpo JSON similar a:

   ```json
   {
     "name": "contrato.pdf",
     "mime_type": "application/pdf",
     "size": 34567,
     "company": "<uuid-de-la-compania>",
     "entity_reference": "<uuid-de-la-referencia>",
     "validation_flow": {
       "steps": [
         {"order": 1, "approver": "<uuid-aprobador-1>"},
         {"order": 2, "approver": "<uuid-aprobador-2>"}
       ]
     }
   }
   ```

   La respuesta incluirá `upload_url` y `upload_token`. El documento aún no se crea en la base de datos.

2. **Subir el archivo real.**
   Utiliza Postman (o una herramienta similar) para hacer `PUT` a `upload_url` con el archivo binario, configurando el encabezado `Content-Type` según `mime_type`.

3. **Confirmar la carga.**
   Una vez completada la subida, confirma con `POST http://localhost:8000/api/documents/complete-upload/` enviando:

   ```json
   {
     "upload_token": "<token-devuelto-en-el-paso-1>"
   }
   ```

   Si el archivo existe en el bucket, se crea el registro definitivo y la respuesta devuelve el documento persistido.

### Descarga del documento

Con el documento creado, solicita `GET http://localhost:8000/api/documents/<id>/download/` para obtener una URL firmada temporal que permite descargar el archivo desde el bucket.


## Notas

- El proyecto usa `django-storages` con Google Cloud Storage como backend de archivos. La caducidad de las URLs firmadas puede ajustarse mediante la variable `GCS_SIGNED_URL_EXPIRES`.
- Para entornos productivos recuerda desactivar `DEBUG` en `.env` y definir un conjunto de `ALLOWED_HOSTS` específico.

## Pruebas automatizadas

Ejecuta la suite de tests con:

```bash
python api/manage.py test documents
```