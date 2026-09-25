# EduFlex

Plataforma web que combina inteligencia artificial y análisis visual en tiempo real para apoyar a niños con dificultades de aprendizaje. Mientras el niño juega, la cámara del navegador analiza su rostro (somnolencia/distracción) y genera reportes automáticos que padres y profesores pueden revisar.

Proyecto de titulación (Ingeniería en Software, UNEMI).

## Integrantes

- Jean Carlos Suárez Acevedo
- Ricardo Alexander Díaz Rivas
- Francisco Javier Ronquillo Jiménez

## Características

- **Detección en tiempo real** de somnolencia y distracción usando MediaPipe Face Mesh, corriendo sobre frames capturados directamente desde la cámara del navegador (no depende de una webcam en el servidor).
- **Juegos educativos** interactivos (sopa de palabras, cartas, multiplicaciones) que registran progreso y puntaje.
- **Sistema de avatar**: el niño desbloquea prendas de ropa como recompensa por sus puntos y personaliza su personaje.
- **Panel de profesor**: creación de cursos, gestión de estudiantes, estadísticas por niño/curso y reportes con evidencia visual.
- **Reportes con evidencia**: capturas de los momentos de somnolencia/distracción almacenadas de forma privada (Cloudinary, URLs firmadas temporales).
- Autenticación propia por sesión (sin `django.contrib.auth`), contraseñas con hash seguro (PBKDF2).
- Recuperación de contraseña por correo.

## Stack técnico

- **Backend**: Django 5
- **Base de datos**: PostgreSQL
- **Visión por computadora**: MediaPipe, OpenCV
- **Almacenamiento de medios**: Cloudinary (fotos de perfil públicas, capturas de detección privadas con URL firmada)
- **Frontend**: HTML/CSS/JS, captura de cámara vía `getUserMedia`
- **Despliegue**: Render + Gunicorn + WhiteNoise

## Arquitectura de la detección

El análisis facial corre por frame (no en video continuo): el navegador captura una imagen cada ~1.8s con `getUserMedia` + `<canvas>` y la envía al servidor. El estado de cada sesión de juego (contadores, eventos confirmados) se guarda en la sesión de Django, lo que permite que varios niños jueguen al mismo tiempo sin interferir entre sí y sin depender de hilos ni estado global en memoria.

## Instalación local

1. Clonar el repositorio y crear un entorno virtual (Python 3.12 recomendado):

   ```bash
   python -m venv venv
   venv\Scripts\activate     # Windows
   source venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   ```

2. Crear una base de datos PostgreSQL vacía.

3. Crear un archivo `.env` en la raíz del proyecto con tus propios valores:

   ```env
   SECRET_KEY=una-clave-secreta-generada-por-ti
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost

   DB_NAME=nombre_base_datos
   DB_USER=usuario_base_datos
   DB_PASSWORD=contraseña_base
   DB_HOST=localhost
   DB_PORT=5432

   EMAIL_HOST_USER=tu_correo@gmail.com
   EMAIL_HOST_PASSWORD=contraseña_de_aplicacion_gmail

   CLOUDINARY_CLOUD_NAME=tu_cloud_name
   CLOUDINARY_API_KEY=tu_api_key
   CLOUDINARY_API_SECRET=tu_api_secret
   ```

4. Migrar y correr el servidor:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Roles

- **Niño**: juega, ve su progreso y personaliza su avatar.
- **Profesor**: crea cursos, agrega estudiantes y revisa reportes/estadísticas.

## Desplegar en Render (gratis)

En [render.com](https://render.com):

1. **New +** → **PostgreSQL**, plan gratuito. Cuando esté listo, copia su
   **Internal Database URL**.
2. **New +** → **Web Service** → conecta este repositorio de GitHub.
   Render detecta el `Dockerfile` automáticamente (Environment: Docker).
   Elige el plan **Free**.
3. En **Environment**, agrega las variables:

   ```
   SECRET_KEY=una-clave-secreta-nueva-y-distinta-a-la-de-tu-.env-local
   DEBUG=False
   ALLOWED_HOSTS=tu-servicio.onrender.com
   CSRF_TRUSTED_ORIGINS=https://tu-servicio.onrender.com
   DATABASE_URL=(la Internal Database URL del paso 1)

   EMAIL_HOST_USER=tu_correo@gmail.com
   EMAIL_HOST_PASSWORD=contraseña_de_aplicacion_gmail

   CLOUDINARY_CLOUD_NAME=tu_cloud_name
   CLOUDINARY_API_KEY=tu_api_key
   CLOUDINARY_API_SECRET=tu_api_secret
   ```

   `tu-servicio` es el subdominio que Render asigna a tu Web Service (lo ves
   arriba del panel una vez creado).

4. Despliega. El contenedor corre las migraciones automáticamente al
   arrancar y luego levanta el servidor.

El plan gratuito de Render se "duerme" tras 15 minutos sin uso y tarda unos
segundos en despertar en la siguiente visita.
