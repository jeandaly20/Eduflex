// Captura periódica de la cámara del navegador para la detección de
// somnolencia/distracción. Reemplaza la antigua captura de webcam del
// SERVIDOR (que no existe en un hosting en la nube): aquí la cámara la
// abre el navegador del alumno y se manda un frame cada cierto intervalo
// al backend, que analiza uno a la vez (ver NIÑO/views.py RecibirFrameDeteccionView).

const DETECCION_INTERVALO_MS = 1800; // debe ser parecido a DETECCION_FRAME_INTERVAL_MS en settings

let _deteccionStream = null;
let _deteccionIntervalId = null;
let _deteccionVideo = null;
let _deteccionCanvas = null;

function iniciarDeteccionCamara(frameUrl) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.warn("Este navegador no soporta cámara; la detección queda desactivada.");
    return;
  }

  navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false })
    .then(stream => {
      _deteccionStream = stream;

      _deteccionVideo = document.createElement('video');
      _deteccionVideo.srcObject = stream;
      _deteccionVideo.playsInline = true;
      _deteccionVideo.muted = true;
      _deteccionVideo.style.display = 'none';
      document.body.appendChild(_deteccionVideo);
      _deteccionVideo.play().catch(() => {});

      _deteccionCanvas = document.createElement('canvas');
      _deteccionCanvas.width = 320;
      _deteccionCanvas.height = 240;

      _deteccionIntervalId = setInterval(() => {
        enviarFrameDeteccion(frameUrl);
      }, DETECCION_INTERVALO_MS);
    })
    .catch(err => {
      // Si el alumno no da permiso de cámara, el juego debe seguir
      // funcionando igual: la detección es un extra, no un requisito.
      console.warn("No se pudo acceder a la cámara, la detección queda desactivada:", err);
    });
}

function enviarFrameDeteccion(frameUrl) {
  if (!_deteccionVideo || !_deteccionCanvas || _deteccionVideo.readyState < 2) {
    return;
  }

  const ctx = _deteccionCanvas.getContext('2d');
  ctx.drawImage(_deteccionVideo, 0, 0, _deteccionCanvas.width, _deteccionCanvas.height);

  _deteccionCanvas.toBlob(blob => {
    if (!blob) return;

    const datos = new FormData();
    datos.append('frame', blob, 'frame.jpg');

    fetch(frameUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: datos,
    }).catch(err => {
      console.warn("No se pudo enviar el frame de detección:", err);
    });
  }, 'image/jpeg', 0.7);
}

function detenerDeteccionCamara() {
  if (_deteccionIntervalId) {
    clearInterval(_deteccionIntervalId);
    _deteccionIntervalId = null;
  }
  if (_deteccionStream) {
    _deteccionStream.getTracks().forEach(track => track.stop());
    _deteccionStream = null;
  }
  if (_deteccionVideo) {
    _deteccionVideo.remove();
    _deteccionVideo = null;
  }
}

window.addEventListener('pagehide', detenerDeteccionCamara);

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => {
  if (typeof frameUrl !== 'undefined' && frameUrl) {
    iniciarDeteccionCamara(frameUrl);
  }
});
