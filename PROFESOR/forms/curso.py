from django import forms
from PROFESOR.models import Curso

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['nombre_curso', 'seccion', 'descripcion', 'periodo', 'fecha_inicio', 'fecha_final']
        widgets = {
            'nombre_curso': forms.TextInput(attrs={'placeholder': 'Ej.2B','id':'nombre_curso'}),
            'seccion': forms.Select(attrs={'placeholder': 'Ej. Matutina','id':'seccion'}),
            'descripcion': forms.Textarea(attrs={'placeholder': 'Descripción breve','id':'descripcion', 'rows': 3}),
            'periodo': forms.TextInput(attrs={'placeholder': 'ej. 2025-2026','id':'periodo'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'id': 'fecha_inicio'}),
            'fecha_final': forms.DateInput(attrs={'type': 'date', 'id': 'fecha_final'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El modelo las permite en blanco (para cursos creados desde el admin),
        # pero acá se exigen: reportEstudiante filtra reportes por este rango
        # de fechas y con null falla.
        self.fields['fecha_inicio'].required = True
        self.fields['fecha_final'].required = True

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        final = cleaned_data.get('fecha_final')
        if inicio and final and final < inicio:
            self.add_error('fecha_final', 'La fecha final no puede ser anterior a la de inicio.')
        return cleaned_data