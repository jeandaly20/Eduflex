import cv2
import mediapipe as mp
from scipy.spatial import distance as dist

# Parámetros
EYE_AR_THRESH = 0.20

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_IRIS = [469, 470, 471, 472]
RIGHT_IRIS = [474, 475, 476, 477]

mp_face_mesh = mp.solutions.face_mesh
# static_image_mode=True: cada frame llega por HTTP de forma independiente
# (no es un stream continuo), así que no tiene sentido el tracking entre frames.
_face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True, static_image_mode=True)


def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    return (A + B) / (2.0 * C)


def get_iris_position(iris_points, eye_points):
    iris_center_x = sum(p[0] for p in iris_points) / len(iris_points)
    eye_left = eye_points[0][0]
    eye_right = eye_points[3][0]
    pos = (iris_center_x - eye_left) / (eye_right - eye_left)

    if pos < 0.35:
        return "derecha"
    elif pos > 0.65:
        return "izquierda"
    else:
        return "centro"


def analizar_frame(frame_bgr):
    """Analiza un único frame (imagen decodificada con OpenCV) y devuelve
    las métricas crudas: si hay rostro, el EAR (para somnolencia) y si el
    niño está mirando al frente (para distracción). No mantiene estado.
    """
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    resultados = _face_mesh.process(rgb)

    if not resultados.multi_face_landmarks:
        return {"rostro_detectado": False, "ear": None, "mirando_frente": None}

    mesh = resultados.multi_face_landmarks[0].landmark

    left_eye = [(int(mesh[i].x * w), int(mesh[i].y * h)) for i in LEFT_EYE]
    right_eye = [(int(mesh[i].x * w), int(mesh[i].y * h)) for i in RIGHT_EYE]
    left_iris = [(int(mesh[i].x * w), int(mesh[i].y * h)) for i in LEFT_IRIS]
    right_iris = [(int(mesh[i].x * w), int(mesh[i].y * h)) for i in RIGHT_IRIS]

    left_ear = eye_aspect_ratio(left_eye)
    right_ear = eye_aspect_ratio(right_eye)
    ear = (left_ear + right_ear) / 2.0

    mirada_izq = get_iris_position(left_iris, left_eye)
    mirada_der = get_iris_position(right_iris, right_eye)
    mirando_frente = mirada_izq == "centro" and mirada_der == "centro"

    return {"rostro_detectado": True, "ear": ear, "mirando_frente": mirando_frente}


def estado_inicial():
    """Estado de una sesión de detección en curso. Es JSON-serializable
    a propósito: vive en request.session (respaldada por Postgres), nunca
    en una variable global de módulo, para que sea seguro con varios
    niños jugando a la vez en distintos workers de gunicorn.
    """
    return {
        "counter_somnolencia": 0,
        "counter_distraccion": 0,
        "en_progreso_somnolencia": False,
        "en_progreso_distraccion": False,
        "inicio_somnolencia": None,
        "inicio_distraccion": None,
        "conteo_somnolencia": 0,
        "conteo_distraccion": 0,
        "tiempos_somnolencia": [],
        "tiempos_distraccion": [],
        "frames_somnolencia": [],
        "frames_distraccion": [],
    }


def evaluar_estado(resultado_frame, estado, now, consec_samples):
    """Actualiza `estado` con una nueva muestra recibida del navegador.

    Devuelve (estado, eventos): `eventos` indica si en esta muestra se
    confirmó el INICIO de un episodio nuevo de somnolencia/distracción
    (momento en el que hay que guardar una captura), para no acoplar esta
    función a S3/almacenamiento.
    """
    eventos = {"nueva_captura_somnolencia": False, "nueva_captura_distraccion": False}

    if not resultado_frame.get("rostro_detectado"):
        return estado, eventos

    ear = resultado_frame["ear"]
    mirando_frente = resultado_frame["mirando_frente"]

    # ---------- Distracción ----------
    if not mirando_frente:
        if not estado["en_progreso_distraccion"]:
            estado["counter_distraccion"] += 1
            if estado["counter_distraccion"] >= consec_samples:
                estado["conteo_distraccion"] += 1
                estado["en_progreso_distraccion"] = True
                estado["inicio_distraccion"] = now
                estado["counter_distraccion"] = 0
                eventos["nueva_captura_distraccion"] = True
    else:
        if estado["en_progreso_distraccion"] and estado["inicio_distraccion"]:
            duracion = round(now - estado["inicio_distraccion"], 2)
            estado["tiempos_distraccion"].append(duracion)
            estado["inicio_distraccion"] = None
        estado["en_progreso_distraccion"] = False
        estado["counter_distraccion"] = 0

    # ---------- Somnolencia ----------
    if ear is not None and ear < EYE_AR_THRESH:
        if not estado["en_progreso_somnolencia"]:
            estado["counter_somnolencia"] += 1
            if estado["counter_somnolencia"] >= consec_samples:
                estado["conteo_somnolencia"] += 1
                estado["en_progreso_somnolencia"] = True
                estado["inicio_somnolencia"] = now
                estado["counter_somnolencia"] = 0
                eventos["nueva_captura_somnolencia"] = True
    else:
        if estado["en_progreso_somnolencia"] and estado["inicio_somnolencia"]:
            duracion = round(now - estado["inicio_somnolencia"], 2)
            estado["tiempos_somnolencia"].append(duracion)
            estado["inicio_somnolencia"] = None
        estado["en_progreso_somnolencia"] = False
        estado["counter_somnolencia"] = 0

    return estado, eventos


def cerrar_estado(estado, now):
    """Cierra cualquier episodio todavía abierto al terminar el juego."""
    if estado["inicio_somnolencia"]:
        estado["tiempos_somnolencia"].append(round(now - estado["inicio_somnolencia"], 2))
        estado["inicio_somnolencia"] = None
    if estado["inicio_distraccion"]:
        estado["tiempos_distraccion"].append(round(now - estado["inicio_distraccion"], 2))
        estado["inicio_distraccion"] = None
    return estado
