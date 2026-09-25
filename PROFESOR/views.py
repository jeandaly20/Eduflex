from django.shortcuts import redirect, get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView,ListView,CreateView
from django.urls import reverse_lazy
from django.db.models import Q
from PROFESOR.models import  Profesor,Curso
from PROFESOR.forms.curso import CursoForm
from NIÑO.models import  Reporte,Niño
import  statistics,operator
from functools import reduce
from datetime import timedelta
from django.conf import settings
from EDUFLEX.storage_backends import CapturaPrivadaStorage
class DashboardTeacher(TemplateView):
    template_name = 'dashboardTeacher.html'

    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profesor_id = self.request.session.get('profesor_id')
        profesor = get_object_or_404(Profesor, id=profesor_id)
        cursos=Curso.objects.filter(profesor=profesor_id)
        context['cursos'] = cursos
        context['profesor'] = profesor
        context['total_cursos'] = cursos.count()
        context['total_estudiantes'] = Niño.objects.filter(cursos__in=cursos).distinct().count()
        return context

class CursoTeacher(TemplateView):
    template_name = 'tus_cursos.html'

    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profesor_id = self.request.session.get('profesor_id')
        curso_profesor=Curso.objects.filter(profesor=profesor_id)
        context['cursos'] = curso_profesor
        return context

class CrearCursoView(CreateView):
    model = Curso
    form_class = CursoForm
    template_name = 'crear_curso.html'

    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.profesor_id = self.request.session.get('profesor_id')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('profesor:agregar_estudiante', kwargs={'curso_id': self.object.id})


class AgregarEstudianteView(View):
    template_name = 'agregar_estudiante.html'

    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, curso_id):
        curso = get_object_or_404(Curso, pk=curso_id, profesor_id=request.session.get('profesor_id'))
        busqueda = request.GET.get('q', '').strip()
        resultados = []

        if busqueda:
            resultados = Niño.objects.filter(
                Q(nombres__icontains=busqueda) | Q(apellidos__icontains=busqueda) | Q(usuario__icontains=busqueda)
            ).exclude(pk__in=curso.niños.values_list('id', flat=True))[:20]

        return render(request, self.template_name, {
            'curso': curso,
            'busqueda': busqueda,
            'resultados': resultados,
        })

    def post(self, request, curso_id):
        curso = get_object_or_404(Curso, pk=curso_id, profesor_id=request.session.get('profesor_id'))
        niño_id = request.POST.get('niño_id')
        if niño_id:
            niño = get_object_or_404(Niño, pk=niño_id)
            curso.niños.add(niño)
        busqueda = request.POST.get('q', '')
        return redirect(f"{request.path}?q={busqueda}")


class PresentarCursoTeacher(ListView):
    template_name = 'curso_estudiante.html'
    context_object_name = 'niños'
    pk_url_kwarg = 'curso_id'

    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        pk = self.kwargs.get(self.pk_url_kwarg)
        curso = get_object_or_404(Curso, pk=pk)
        queryset = curso.niños.all()

        nombre = self.request.GET.get('nombre', '').strip()
        genero = self.request.GET.get('genero')

        if nombre:
            palabras = nombre.split()
            queries = [
                Q(nombres__icontains=palabra) | Q(apellidos__icontains=palabra)
                for palabra in palabras
            ]
            queryset = queryset.filter(reduce(operator.and_, queries))
        if genero:
            queryset = queryset.filter(genero=genero)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        curso = get_object_or_404(Curso, pk=self.kwargs.get(self.pk_url_kwarg))
        context['curso'] = curso
        context['nombre'] = self.request.GET.get('nombre', '')
        context['genero'] = self.request.GET.get('genero', '')
        return context

class reportEstudiante(TemplateView):
    template_name = 'reporte_niño.html'
    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        niño_id = self.kwargs.get('niño_id')
        curso_id = self.kwargs.get('curso_id')
        curso=Curso.objects.get(pk=curso_id)
        nino = Niño.objects.get(pk=niño_id)
        context['nino'] = nino
        context['curso'] = curso
        context['reportes'] = Reporte.objects.filter(
            niño=nino, puntaje__isnull=False, fecha__range=(curso.fecha_inicio, curso.fecha_final)
        ).order_by('-fecha')
        return context


class verReportStudent(TemplateView):
        template_name = 'verReportStudent.html'
        def dispatch(self, request, *args, **kwargs):
            if 'profesor_id' not in request.session:
                return redirect('accounts:login')
            return super().dispatch(request, *args, **kwargs)
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            reporte_id = self.kwargs.get('reporte_id')
            reporte = Reporte.objects.get(pk=reporte_id)
            nino_id = reporte.niño.id
            nino= Niño.objects.get(pk=nino_id)
            curso_id = self.kwargs.get('curso_id')
            curso= Curso.objects.get(pk=curso_id)
            # Las capturas viven en Cloudinary como recursos privados; acá se
            # firma una URL temporal por cada una, solo válida mientras se ve
            # este reporte (ver EDUFLEX/storage_backends.CapturaPrivadaStorage).
            captura_storage = CapturaPrivadaStorage()
            frames_somnolencia = [captura_storage.url(key) for key in (reporte.frames_somnolencia or [])]
            frames_distraccion = [captura_storage.url(key) for key in (reporte.frames_distraccion or [])]

            pares_somnolencia = zip(frames_somnolencia, reporte.tiempos_somnolencia or [])
            pares_distraccion = zip(frames_distraccion, reporte.tiempos_distraccion or [])
            promedio_somnolencia = round(statistics.mean(reporte.tiempos_somnolencia),
                                         2) if reporte.tiempos_somnolencia else 0
            promedio_distraccion = round(statistics.mean(reporte.tiempos_distraccion),
                                         2) if reporte.tiempos_distraccion else 0
            total_somnolencia = sum(reporte.tiempos_somnolencia or [])
            total_distraccion = sum(reporte.tiempos_distraccion or [])
            tiempo_concentracion = (
                    reporte.duracion_evaluacion
                    - timedelta(seconds=total_somnolencia)
                    - timedelta(seconds=total_distraccion)
            )
            context['nino'] = nino
            context['curso']=curso
            context['reporte'] = reporte
            context['puntaje']= round((reporte.puntaje or 0) / 10, 2)
            context['pares_somnolencia'] = list(pares_somnolencia)
            context['pares_distraccion'] = list(pares_distraccion)
            context['promedio_somnolencia'] = promedio_somnolencia
            context['promedio_distraccion'] = promedio_distraccion
            context['total_somnolencia'] = total_somnolencia
            context['total_distraccion'] = total_distraccion
            context['tiempo_concentracion'] = tiempo_concentracion
            context['grafico_data'] = {
                'distracciones': reporte.distracciones or 0,
                'somnolencias': reporte.somnolencias or 0,
                'tiempos_somnolencia': reporte.tiempos_somnolencia or [],
                'tiempos_distraccion': reporte.tiempos_distraccion or [],
            }

            return context


class Estadisticas_niño(TemplateView):
    template_name = "estadisticas_generales_niño.html"
    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        niño_id = self.kwargs.get('niño_id')
        curso_id = self.kwargs.get('curso_id')
        nino = get_object_or_404(Niño, pk=niño_id)
        reportes = Reporte.objects.filter(niño=nino, puntaje__isnull=False)
        curso=get_object_or_404(Curso, pk=curso_id)
        nivel = self.request.GET.get('nivel')
        fecha_i = self.request.GET.get('fecha_i')
        fecha_f = self.request.GET.get('fecha_f')

        if nivel:
            reportes = reportes.filter(titulo__icontains=f'nivel {nivel}')
        if fecha_i and fecha_f:
            reportes = reportes.filter(fecha__range=[fecha_i, fecha_f])
        elif fecha_i:
            reportes = reportes.filter(fecha__gte=fecha_i)
        elif fecha_f:
            reportes = reportes.filter(fecha__lte=fecha_f)

        total_distracciones = sum(r.distracciones or 0 for r in reportes)
        total_somnolencias = sum(r.somnolencias or 0 for r in reportes)
        cantidad_reportes = reportes.count()
        puntajes = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'puntaje': round(float(r.puntaje) / 10, 2) if r.puntaje is not None else 0
            }
            for r in reportes
        ]
        distracciones = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'distracciones': int(r.distracciones) if r.distracciones is not None else 0
            }
            for r in reportes
        ]
        somnolencias = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'somnolencias': int(r.somnolencias) if r.somnolencias is not None else 0
            }
            for r in reportes
        ]
        tiempos_distraccion_sumados = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'tiempo_total_distraccion': float(sum(r.tiempos_distraccion or []))
            }
            for r in reportes
        ]
        tiempos_somnolencia_sumados = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'tiempo_total_somnolencia': float(sum(r.tiempos_somnolencia or []))
            }
            for r in reportes
        ]
        tiempos = [r['tiempo_total_distraccion'] for r in tiempos_distraccion_sumados]
        promedio_tiempo_distraccion = round(statistics.mean(tiempos), 2) if tiempos else 0
        tiempos_som = [r['tiempo_total_somnolencia'] for r in tiempos_somnolencia_sumados]
        promedio_tiempo_somnolencia = round(statistics.mean(tiempos_som), 2) if tiempos_som else 0
        solo_puntajes = [p['puntaje'] for p in puntajes]
        promedio_puntaje = round(statistics.mean(solo_puntajes), 2) if solo_puntajes else 0
        promedio_distracciones = round(total_distracciones / cantidad_reportes, 2) if cantidad_reportes > 0 else 0
        promedio_somnolencias = round(total_somnolencias / cantidad_reportes, 2) if cantidad_reportes > 0 else 0
        context['nino'] = nino
        context['reportes'] = reportes
        context['total_distracciones'] = total_distracciones
        context['total_somnolencias'] = total_somnolencias
        context['nivel'] = nivel or ''
        context['fecha_i'] = fecha_i or ''
        context['fecha_f'] = fecha_f or ''
        context['promedio_distracciones'] = promedio_distracciones
        context['promedio_somnolencias'] = promedio_somnolencias
        context['promedio_puntaje'] = promedio_puntaje
        context['distracciones'] = distracciones
        context['somnolencias'] = somnolencias
        context['puntajes'] = puntajes
        context['tiempos_distraccion_sumados'] = tiempos_distraccion_sumados
        context['tiempos_somnolencia_sumados'] = tiempos_somnolencia_sumados
        context['promedio_tiempo_distraccion'] = promedio_tiempo_distraccion
        context['promedio_tiempo_somnolencia'] = promedio_tiempo_somnolencia
        context['curso'] = curso
        context['graficodis_som'] = {
            'distracciones': total_distracciones,
            'somnolencias': total_somnolencias,
        }
        return context

class Estadisticas_curso(TemplateView):
    template_name = "estadisticas_generales_curso.html"
    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        curso_id = self.kwargs.get('curso_id')
        curso = get_object_or_404(Curso, pk=curso_id)
        niños = curso.niños.all()
        reportes = Reporte.objects.filter(niño__in=niños, puntaje__isnull=False)

        nivel = self.request.GET.get('nivel')
        fecha_i = self.request.GET.get('fecha_i')
        fecha_f = self.request.GET.get('fecha_f')

        if nivel:
            reportes = reportes.filter(titulo__icontains=f'nivel {nivel}')
        if fecha_i and fecha_f:
            reportes = reportes.filter(fecha__range=[fecha_i, fecha_f])
        elif fecha_i:
            reportes = reportes.filter(fecha__gte=fecha_i)
        elif fecha_f:
            reportes = reportes.filter(fecha__lte=fecha_f)

        total_distracciones = sum(r.distracciones or 0 for r in reportes)
        total_somnolencias = sum(r.somnolencias or 0 for r in reportes)
        cantidad_reportes = reportes.count()
        solo_puntajes = [float(r.puntaje) / 10 for r in reportes if r.puntaje is not None]
        promedio_puntaje = round(statistics.mean(solo_puntajes), 2) if solo_puntajes else 0
        promedio_distracciones = round(total_distracciones / cantidad_reportes, 2) if cantidad_reportes > 0 else 0
        promedio_somnolencias = round(total_somnolencias / cantidad_reportes, 2) if cantidad_reportes > 0 else 0

        puntajes_por_fecha = {}
        conteo_por_fecha = {}

        for r in reportes:
            fecha_str = r.fecha.strftime('%Y-%m-%d')
            puntaje = float(r.puntaje) / 10 if r.puntaje is not None else 0
            if fecha_str in puntajes_por_fecha:
                puntajes_por_fecha[fecha_str] += puntaje
                conteo_por_fecha[fecha_str] += 1
            else:
                puntajes_por_fecha[fecha_str] = puntaje
                conteo_por_fecha[fecha_str] = 1


        puntajes = [
            {'fecha': fecha, 'puntaje': round(puntajes_por_fecha[fecha] / conteo_por_fecha[fecha], 2)}
            for fecha in puntajes_por_fecha
        ]

        distracciones = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'distracciones': int(r.distracciones) if r.distracciones is not None else 0
            }
            for r in reportes
        ]
        somnolencias = [
            {
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'somnolencias': int(r.somnolencias) if r.somnolencias is not None else 0
            }
            for r in reportes
        ]

        tiempos_somnolencia_por_fecha = {}
        for r in reportes:
            fecha_str = r.fecha.strftime('%Y-%m-%d')
            suma_somnolencia = float(sum(r.tiempos_somnolencia or []))
            if fecha_str in tiempos_somnolencia_por_fecha:
                tiempos_somnolencia_por_fecha[fecha_str] += suma_somnolencia
            else:
                tiempos_somnolencia_por_fecha[fecha_str] = suma_somnolencia
        tiempos_somnolencia_sumados = [
            {'fecha': fecha, 'tiempo_total_somnolencia': tiempo}
            for fecha, tiempo in tiempos_somnolencia_por_fecha.items()
        ]
        tiempos_distraccion_por_fecha = {}
        for r in reportes:
            fecha_str = r.fecha.strftime('%Y-%m-%d')
            suma_distraccion = float(sum(r.tiempos_distraccion or []))
            if fecha_str in tiempos_distraccion_por_fecha:
                tiempos_distraccion_por_fecha[fecha_str] += suma_distraccion
            else:
                tiempos_distraccion_por_fecha[fecha_str] = suma_distraccion
        tiempos_distraccion_sumados = [
            {'fecha': fecha, 'tiempo_total_distraccion': tiempo}
            for fecha, tiempo in tiempos_distraccion_por_fecha.items()
        ]
        tiempos_distraccion = [sum(r.tiempos_distraccion or []) for r in reportes]
        tiempos_somnolencia = [sum(r.tiempos_somnolencia or []) for r in reportes]
        promedio_tiempo_distraccion = round(statistics.mean(tiempos_distraccion), 2) if tiempos_distraccion else 0
        promedio_tiempo_somnolencia = round(statistics.mean(tiempos_somnolencia), 2) if tiempos_somnolencia else 0
        context['curso'] = curso
        context['total_distracciones'] = total_distracciones
        context['total_somnolencias'] = total_somnolencias
        context['promedio_puntaje'] = promedio_puntaje
        context['promedio_distracciones'] = promedio_distracciones
        context['promedio_somnolencias'] = promedio_somnolencias
        context['cantidad_reportes'] = cantidad_reportes
        context['reportes'] = reportes
        context['nivel'] = nivel or ''
        context['fecha_i'] = fecha_i or ''
        context['fecha_f'] = fecha_f or ''
        context['promedio_tiempo_distraccion'] = promedio_tiempo_distraccion
        context['promedio_tiempo_somnolencia'] = promedio_tiempo_somnolencia
        context['tiempos_somnolencia_sumados'] = tiempos_somnolencia_sumados
        context['tiempos_distraccion_sumados'] = tiempos_distraccion_sumados


        context['puntajes'] = puntajes
        context['distracciones'] = distracciones
        context['somnolencias'] = somnolencias
        context['graficodis_som'] = {
            'distracciones': total_distracciones,
            'somnolencias': total_somnolencias,
        }

        return context
class GuardarComentarios(View):
    def dispatch(self, request, *args, **kwargs):
        if 'profesor_id' not in request.session:
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        reporte_id = request.POST.get('reporte_id')
        curso_id=request.POST.get('curso_id')
        comentario = request.POST.get('comentario')
        reporte = get_object_or_404(Reporte, pk=reporte_id)
        reporte.comentario = comentario
        reporte.save()

        return redirect('profesor:verReportStudent',reporte_id=reporte_id,curso_id=curso_id)
