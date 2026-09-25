from django.urls import path
from PROFESOR.views import *
app_name = 'profesor'
urlpatterns = [
    path('dashboardTeacher/',DashboardTeacher.as_view(),name='dashboardTeacher'),
    path('tuscursos/',CursoTeacher.as_view(),name='tuscursos'),
    path('curso/crear/',CrearCursoView.as_view(),name='crear_curso'),
    path('curso/<int:curso_id>/',PresentarCursoTeacher.as_view(),name='curso'),
    path('curso/<int:curso_id>/agregar_estudiante/',AgregarEstudianteView.as_view(),name='agregar_estudiante'),
    path('estudiante/<int:curso_id>/<int:niño_id>', reportEstudiante.as_view(), name='estudiante'),
    path('verReportStudent/<int:reporte_id>/<int:curso_id>', verReportStudent.as_view(), name='verReportStudent'),
    path('statsKid/<int:niño_id>/<int:curso_id>/', Estadisticas_niño.as_view(),name='verEstadisticasNiño'),
    path('statsCourse/<int:curso_id>/',Estadisticas_curso.as_view(), name='verEstadisticasCurso'),
    path('guardar_comentario/', GuardarComentarios.as_view(), name='guardar_comentario'),
]