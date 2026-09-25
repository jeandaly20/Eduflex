import time

import cv2
import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from decimal import Decimal
from .models import ProgresoNiño
from NIÑO.models import Niño,Reporte
from NIÑO.modelo_deteccion import analizar_frame, estado_inicial, evaluar_estado, cerrar_estado
from NIÑO.avatar_catalog import calcular_puntos_totales, catalogo_con_estado, colores_equipados, CAMPO_POR_CATEGORIA
from EDUFLEX.storage_backends import CapturaPrivadaStorage
from datetime import datetime
from datetime import timedelta
from .models import ProgresoNiño, ProgresoCartas,ProgresoDiscalculia
from .models import PreferenciasUsuario
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def _deteccion_session_key(reporte_id):
    return f"deteccion_estado_{reporte_id}"


def _iniciar_deteccion(request, reporte_id):
    request.session[_deteccion_session_key(reporte_id)] = estado_inicial()
    request.session.modified = True


def _cerrar_reporte_deteccion(request, reporte, nino_id, extra_fields=None):
    """Cierra el estado de detección en sesión (si existe) y copia los
    resultados acumulados al `Reporte`. `extra_fields` son los campos
    propios de cada juego (titulo, puntaje, duracion_evaluacion)."""
    key = _deteccion_session_key(reporte.id)
    estado = request.session.get(key)
    if estado is None:
        estado = estado_inicial()
    estado = cerrar_estado(estado, time.time())

    for campo, valor in (extra_fields or {}).items():
        setattr(reporte, campo, valor)

    reporte.somnolencias = estado["conteo_somnolencia"]
    reporte.distracciones = estado["conteo_distraccion"]
    reporte.tiempos_somnolencia = estado["tiempos_somnolencia"]
    reporte.tiempos_distraccion = estado["tiempos_distraccion"]
    reporte.frames_somnolencia = estado["frames_somnolencia"]
    reporte.frames_distraccion = estado["frames_distraccion"]
    reporte.save()

    request.session.pop(key, None)
    request.session[f"deteccion_iniciada_{nino_id}"] = False
    request.session.pop('reporte_id', None)
    request.session.modified = True
    return reporte



class DashboardKid(TemplateView):
    template_name = 'dashboardKid.html'

    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def formatear_tiempo(td: timedelta) -> str:
        total_segundos = int(td.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60

        partes = []
        if horas > 0:
            partes.append(f"{horas}h")
        if minutos > 0 or horas > 0:
            partes.append(f"{minutos}m")
        partes.append(f"{segundos}s")

        return " ".join(partes)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nino_id = self.request.session.get('nino_id')
        niño = Niño.objects.get(pk=nino_id)
        context['niño'] = niño

        total_niveles = 5


        if niño.especialidad == 'T':
            progreso = ProgresoCartas.objects.filter(niño=niño).first()
        else:
            progreso = ProgresoNiño.objects.filter(niño=niño).first()

        nivel_desbloqueado = progreso.nivel_desbloqueado if progreso else 1


        reportes_validos = Reporte.objects.filter(niño=niño, puntaje__gte=70)

        niveles_completados = set()
        records_dict = {}

        for rep in reportes_validos:
            try:
                nivel = int(rep.titulo.split()[-1])
            except (AttributeError, ValueError, IndexError):
                continue

            niveles_completados.add(nivel)

            if nivel not in records_dict:
                records_dict[nivel] = {
                    'nivel': nivel,
                    'puntaje': int(rep.puntaje),
                    'tiempo': self.formatear_tiempo(rep.duracion_evaluacion),
                    'duracion': rep.duracion_evaluacion
                }
            else:
                record_actual = records_dict[nivel]
                puntaje_actual = record_actual['puntaje']
                duracion_actual = record_actual['duracion']

                nuevo_puntaje = int(rep.puntaje)
                nueva_duracion = rep.duracion_evaluacion

                if (
                        nuevo_puntaje > puntaje_actual
                        or (nuevo_puntaje == puntaje_actual and nueva_duracion < duracion_actual)
                ):
                    records_dict[nivel] = {
                        'nivel': nivel,
                        'puntaje': nuevo_puntaje,
                        'tiempo': self.formatear_tiempo(nueva_duracion),
                        'duracion': nueva_duracion
                    }

        niveles_completados_count = len(niveles_completados)
        progreso_porcentaje = int((niveles_completados_count / total_niveles) * 100)


        records = sorted([
            {k: v for k, v in record.items() if k != 'duracion'}
            for record in records_dict.values()
        ], key=lambda x: x['nivel'])

        puntos_avatar = calcular_puntos_totales(niño)

        context.update({
            'niño': niño,
            'progreso_completado': niveles_completados_count,
            'total_niveles': total_niveles,
            'progreso_porcentaje': progreso_porcentaje,
            'records': records,
            'niveles_completados': niveles_completados_count,
            'avatar_puntos': int(puntos_avatar),
            'avatar_catalogo': catalogo_con_estado(niño, puntos_avatar),
            'avatar_colores': colores_equipados(niño),
        })

        return context


class JuegosRecomendadosView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        nino_id = request.session.get('nino_id')

        if not nino_id:
            return redirect('accounts:login')

        try:
            nino = get_object_or_404(Niño, pk=nino_id)
            especialidad_niño = nino.especialidad

            juego_a_mostrar = None

            if especialidad_niño == 'D':
                juego_a_mostrar = "Ordena las palabras"
            elif especialidad_niño == 'DC':
                juego_a_mostrar = "Cuenta conmigo"
            elif especialidad_niño == 'T':
                juego_a_mostrar = "Desafío de concentración"

            return render(request, 'juegos.html', {'juego': juego_a_mostrar})

        except Niño.DoesNotExist:
            return render(request, 'juegos.html', {'juego': None})


class niveles_disgrafiaView(View):
    def get(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')
        niño = Niño.objects.get(pk=nino_id)
        progreso, _ = ProgresoNiño.objects.get_or_create(niño=niño)
        return render(request, 'niveles_disgrafia.html', {
            'nivel_desbloqueado': progreso.nivel_desbloqueado
        })


class juego_completar_palabraView(TemplateView):
    template_name = 'completar_palabra.html'

    def dispatch(self, request, *args, **kwargs):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')

        session_key = f"deteccion_iniciada_{nino_id}"
        tiempo_key = f"tiempo_inicio_deteccion_{nino_id}"

        iniciado = request.session.get(session_key, False)
        tiempo_inicio_str = request.session.get(tiempo_key)


        if iniciado and tiempo_inicio_str:
            try:
                tiempo_inicio = datetime.fromisoformat(tiempo_inicio_str)
                if datetime.now() - tiempo_inicio > timedelta(minutes=2):
                    iniciado = False
                    request.session[session_key] = False
                    request.session.pop(tiempo_key, None)
            except Exception:
                iniciado = False
                request.session[session_key] = False
                request.session.pop(tiempo_key, None)

        if not iniciado:
            request.session[session_key] = True
            request.session[tiempo_key] = datetime.now().isoformat()


            niño = Niño.objects.get(pk=nino_id)
            nuevo_reporte = Reporte.objects.create(niño=niño)
            request.session['reporte_id'] = nuevo_reporte.id
            _iniciar_deteccion(request, nuevo_reporte.id)

        return super().dispatch(request, *args, **kwargs)



@method_decorator(csrf_exempt, name='dispatch')
class GuardarProgresoView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({}, status=400)

        try:
            nivel = int(request.POST.get('nivel', 0))
            puntaje = Decimal(request.POST.get('puntaje', '0'))
            tiempo = int(request.POST.get('tiempo', 0))
            puntaje_real = Decimal(puntaje)

            niño = Niño.objects.get(pk=nino_id)
            progreso, _ = ProgresoNiño.objects.get_or_create(niño=niño)


            if puntaje >= 70:
                if nivel + 1 > progreso.nivel_desbloqueado:
                    progreso.nivel_desbloqueado = nivel + 1

            progreso.puntaje_total += puntaje
            progreso.tiempo_total += tiempo
            progreso.save()

            reporte_id = request.session.get('reporte_id')
            if not reporte_id:
                return JsonResponse({}, status=400)

            reporte = Reporte.objects.get(pk=reporte_id)
            _cerrar_reporte_deteccion(request, reporte, nino_id, extra_fields={
                'titulo': f"Digrafia, nivel {nivel}",
                'puntaje': puntaje_real,
                'duracion_evaluacion': timedelta(seconds=tiempo),
            })

            return JsonResponse({'estado': 'ok'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)



@method_decorator(csrf_exempt, name='dispatch')
class GuardarProgresoCartasView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        try:
            nivel = int(request.POST.get('nivel', 0))
            puntaje = int(request.POST.get('puntaje', 0))
            tiempo = int(request.POST.get('tiempo', 0))
            puntaje_real = Decimal(puntaje)

            niño = Niño.objects.get(pk=nino_id)
            progreso, _ = ProgresoCartas.objects.get_or_create(niño=niño)

            if puntaje >= 70:
                if nivel + 1 > progreso.nivel_desbloqueado:
                    progreso.nivel_desbloqueado = nivel + 1

            progreso.puntaje_total += puntaje
            progreso.tiempo_total += tiempo
            progreso.save()

            reporte_id = request.session.get('reporte_id')
            if not reporte_id:
                return JsonResponse({'error': 'ID de reporte no encontrado'}, status=400)

            reporte = Reporte.objects.get(pk=reporte_id)
            _cerrar_reporte_deteccion(request, reporte, nino_id, extra_fields={
                'titulo': f"TDA, nivel {nivel}",
                'puntaje': puntaje_real,
                'duracion_evaluacion': timedelta(seconds=tiempo),
            })

            return JsonResponse({'estado': 'ok'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class juego_cartasView(TemplateView):
    template_name = 'cartas.html'

    def dispatch(self, request, *args, **kwargs):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')

        session_key = f"deteccion_iniciada_{nino_id}"
        tiempo_key = f"tiempo_inicio_deteccion_{nino_id}"

        iniciado = request.session.get(session_key, False)
        tiempo_inicio_str = request.session.get(tiempo_key)

        if iniciado and tiempo_inicio_str:
            try:
                tiempo_inicio = datetime.fromisoformat(tiempo_inicio_str)
                if datetime.now() - tiempo_inicio > timedelta(minutes=2):
                    iniciado = False
                    request.session[session_key] = False
                    request.session.pop(tiempo_key, None)
            except Exception:
                iniciado = False
                request.session[session_key] = False
                request.session.pop(tiempo_key, None)

        if not iniciado:
            request.session[session_key] = True
            request.session[tiempo_key] = datetime.now().isoformat()
            request.session.modified = True


            niño = Niño.objects.get(pk=nino_id)
            nuevo_reporte = Reporte.objects.create(niño=niño)
            request.session['reporte_id'] = nuevo_reporte.id
            _iniciar_deteccion(request, nuevo_reporte.id)

        return super().dispatch(request, *args, **kwargs)


class NivelesCartasView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')

        niño = Niño.objects.get(pk=nino_id)
        progreso, _ = ProgresoCartas.objects.get_or_create(niño=niño)

        return render(request, 'niveles_cartas.html', {
            'nivel_desbloqueado': progreso.nivel_desbloqueado
        })


@method_decorator(csrf_exempt, name='dispatch')
class PreferenciasUsuarioView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        try:
            niño = Niño.objects.get(pk=nino_id)
            preferencias, _ = PreferenciasUsuario.objects.get_or_create(niño=niño)

            return JsonResponse({
                'sonido_activado': preferencias.sonido_activado,
                'texto_grande': preferencias.texto_grande
            })
        except Niño.DoesNotExist:
            return JsonResponse({'error': 'Niño no encontrado'}, status=404)

    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        try:
            niño = Niño.objects.get(pk=nino_id)
            preferencias, _ = PreferenciasUsuario.objects.get_or_create(niño=niño)


            sonido = request.POST.get('sonido_activado')
            texto = request.POST.get('texto_grande')

            if sonido is not None:
                preferencias.sonido_activado = sonido == "true"
            if texto is not None:
                preferencias.texto_grande = texto == "true"

            preferencias.save()

            return JsonResponse({'estado': 'ok'})
        except Niño.DoesNotExist:
            return JsonResponse({'error': 'Niño no encontrado'}, status=404)

@method_decorator(csrf_exempt, name='dispatch')
class EquiparAvatarView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        categoria = request.POST.get('categoria')
        item_id = request.POST.get('item_id', '')

        campo = CAMPO_POR_CATEGORIA.get(categoria)
        if not campo:
            return JsonResponse({'error': 'Categoría inválida'}, status=400)

        try:
            niño = Niño.objects.get(pk=nino_id)
        except Niño.DoesNotExist:
            return JsonResponse({'error': 'Niño no encontrado'}, status=404)

        catalogo = catalogo_con_estado(niño, calcular_puntos_totales(niño))
        item = next((i for i in catalogo[categoria] if i['id'] == item_id), None)

        if item is None:
            return JsonResponse({'error': 'Ítem no existe'}, status=404)
        if not item['desbloqueado']:
            return JsonResponse({'error': 'Todavía no desbloqueas ese ítem'}, status=403)

        setattr(niño, campo, item_id)
        niño.save()

        return JsonResponse({'estado': 'ok', 'categoria': categoria, 'item_id': item_id, 'color': item['color']})


@method_decorator(csrf_exempt, name='dispatch')
class EditarPerfilView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'estado': 'error', 'mensaje': 'No autenticado'}, status=403)

        try:
            niño = Niño.objects.get(pk=nino_id)

            nuevo_usuario = request.POST.get("usuario", "").strip()
            nuevo_email = request.POST.get("email", "").strip()
            nuevos_nombres = request.POST.get("nombres", "").strip()
            nuevos_apellidos = request.POST.get("apellidos", "").strip()

            if nuevo_usuario:
                if Niño.objects.filter(usuario=nuevo_usuario).exclude(pk=niño.pk).exists():
                    return JsonResponse({
                        'estado': 'error',
                        'mensaje': 'Ese nombre de usuario ya está en uso. Intenta con otro.'
                    }, status=400)
                niño.usuario = nuevo_usuario

            if nuevo_email:
                try:
                    validate_email(nuevo_email)
                except ValidationError:
                    return JsonResponse({
                        'estado': 'error',
                        'mensaje': 'El formato del correo electrónico no es válido.'
                    }, status=400)

                if Niño.objects.filter(email=nuevo_email).exclude(pk=niño.pk).exists():
                    return JsonResponse({
                        'estado': 'error',
                        'mensaje': 'Ese correo electrónico ya está en uso. Intenta con otro.'
                    }, status=400)
                niño.email = nuevo_email
            if nuevos_nombres:
                niño.nombres = nuevos_nombres
            if nuevos_apellidos:
                niño.apellidos = nuevos_apellidos

            if 'foto' in request.FILES:
                niño.foto_perfil = request.FILES['foto']

            niño.save()
            return JsonResponse({'estado': 'ok', 'mensaje': 'Perfil actualizado correctamente.'})

        except Niño.DoesNotExist:
            return JsonResponse({'estado': 'error', 'mensaje': 'Niño no encontrado'}, status=404)


class GuardarProgresoMultiplicacionView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def post(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return JsonResponse({'error': 'No autenticado'}, status=403)

        try:
            nivel = int(request.POST.get('nivel', 0))
            puntaje = int(request.POST.get('puntaje', 0))
            tiempo = int(request.POST.get('tiempo', 0))

            niño = Niño.objects.get(pk=nino_id)
            progreso, _ = ProgresoDiscalculia.objects.get_or_create(niño=niño)

            if puntaje >= 70:
                if nivel + 1 > progreso.nivel_desbloqueado:
                    progreso.nivel_desbloqueado = nivel + 1

            progreso.puntaje_total += puntaje
            progreso.tiempo_total += tiempo
            progreso.save()

            puntaje_real = Decimal(puntaje)

            reporte_id = request.session.get('reporte_id')
            if not reporte_id:
                return JsonResponse({'error': 'ID de reporte no encontrado'}, status=400)

            reporte = Reporte.objects.get(pk=reporte_id)
            _cerrar_reporte_deteccion(request, reporte, nino_id, extra_fields={
                'titulo': f"Discalculia, nivel {nivel}",
                'puntaje': puntaje_real,
                'duracion_evaluacion': timedelta(seconds=tiempo),
            })

            return JsonResponse({'estado': 'ok'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class JuegoMultiplicacionView(TemplateView):
    template_name = 'juego_multiplicaciones.html'  # o el nombre real

    def dispatch(self, request, *args, **kwargs):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')

        session_key = f"deteccion_iniciada_{nino_id}"
        tiempo_key = f"tiempo_inicio_deteccion_{nino_id}"

        iniciado = request.session.get(session_key, False)
        tiempo_inicio_str = request.session.get(tiempo_key)

        if iniciado and tiempo_inicio_str:
            try:
                tiempo_inicio = datetime.fromisoformat(tiempo_inicio_str)
                if datetime.now() - tiempo_inicio > timedelta(minutes=2):
                    iniciado = False
                    request.session[session_key] = False
                    request.session.pop(tiempo_key, None)
            except Exception:
                iniciado = False
                request.session[session_key] = False
                request.session.pop(tiempo_key, None)

        if not iniciado:
            request.session[session_key] = True
            request.session[tiempo_key] = datetime.now().isoformat()
            request.session.modified = True

            niño = Niño.objects.get(pk=nino_id)
            nuevo_reporte = Reporte.objects.create(niño=niño)
            request.session['reporte_id'] = nuevo_reporte.id
            _iniciar_deteccion(request, nuevo_reporte.id)

        return super().dispatch(request, *args, **kwargs)

class NivelesDiscalculiaView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get(self, request):
        nino_id = request.session.get('nino_id')
        if not nino_id:
            return redirect('accounts:login')

        niño = Niño.objects.get(pk=nino_id)
        progreso, _ = ProgresoDiscalculia.objects.get_or_create(niño=niño)

        return render(request, 'niveles_discalculia.html', {
            'nivel_desbloqueado': progreso.nivel_desbloqueado
        })


class RecibirFrameDeteccionView(View):
    """Recibe un frame JPEG capturado por la cámara del navegador (ver
    static/JS/deteccion_camara.js), lo analiza y actualiza el estado de
    detección de la sesión en curso. No usa hilos ni estado global: todo
    vive en request.session, por lo que es seguro con varios niños jugando
    a la vez en distintos workers."""

    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return JsonResponse({}, status=204)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        nino_id = request.session.get('nino_id')
        reporte_id = request.session.get('reporte_id')
        frame_file = request.FILES.get('frame')

        if not reporte_id or not frame_file:
            return JsonResponse({}, status=204)

        estado = request.session.get(_deteccion_session_key(reporte_id))
        if estado is None:
            return JsonResponse({}, status=204)

        datos = np.frombuffer(frame_file.read(), dtype=np.uint8)
        frame_bgr = cv2.imdecode(datos, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return JsonResponse({}, status=204)

        resultado_frame = analizar_frame(frame_bgr)
        now = time.time()
        estado, eventos = evaluar_estado(
            resultado_frame, estado, now,
            consec_samples=settings.DETECCION_CONSEC_SAMPLES,
        )
        if eventos["nueva_captura_somnolencia"] or eventos["nueva_captura_distraccion"]:
            tipo = "somnolencia" if eventos["nueva_captura_somnolencia"] else "distraccion"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
            nombre = f"{nino_id}/{reporte_id}/{tipo}_{timestamp}.jpg"
            ok, buffer = cv2.imencode('.jpg', frame_bgr)
            if ok:
                storage = CapturaPrivadaStorage()
                key = storage.save(nombre, ContentFile(buffer.tobytes()))
                if tipo == "somnolencia":
                    estado["frames_somnolencia"].append(key)
                else:
                    estado["frames_distraccion"].append(key)

        request.session[_deteccion_session_key(reporte_id)] = estado
        request.session.modified = True

        return JsonResponse({}, status=204)


class cerrar_juegoView(View):
    def dispatch(self, request, *args, **kwargs):
        if 'nino_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get(self, request):
        niño = None

        reporte_id = request.session.get('reporte_id')
        if reporte_id:
            request.session.pop(_deteccion_session_key(reporte_id), None)
            try:
                niño = Niño.objects.get(pk=request.session.get('nino_id'))
                Reporte.objects.filter(pk=reporte_id).delete()
            except Exception:
                pass
            request.session.pop('reporte_id', None)
            request.session.modified = True


        if niño is None:
            try:
                niño = Niño.objects.get(pk=request.session.get('nino_id'))
            except Niño.DoesNotExist:
                return redirect('niño:seleccionar_nivel')
            except Exception:
                return redirect('niño:seleccionar_nivel')


        if niño.especialidad == 'D':
            return redirect('niño:niveles_disgrafia')
        elif niño.especialidad == 'DC':
            return redirect('niño:niveles_discalculia')
        else:
            return redirect('niño:niveles_cartas')