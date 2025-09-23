"""
Serializers para formularios F29
Módulo separado para mantener organización modular
"""
from rest_framework import serializers


class F29FormularioRequestSerializer(serializers.Serializer):
    """Serializer para solicitud de formulario F29"""
    folio = serializers.CharField(
        max_length=20,
        help_text="Folio del formulario F29"
    )
    periodo = serializers.CharField(
        max_length=6,
        required=False,
        help_text="Período tributario en formato YYYYMM (opcional)"
    )


class ValorFilaSerializer(serializers.Serializer):
    """Serializer para valores individuales en filas F29"""
    code = serializers.CharField()
    value = serializers.CharField()
    name = serializers.CharField(required=False)
    subject = serializers.CharField(required=False)


class FilaDatosSerializer(serializers.Serializer):
    """Serializer para filas de datos del F29"""
    line = serializers.CharField()
    description = serializers.CharField()
    values = ValorFilaSerializer(many=True)


class ColumnasSubtablaSerializer(serializers.Serializer):
    """Serializer para columnas de subtablas F29"""
    title = serializers.CharField()
    columns = serializers.ListField(child=serializers.CharField())


class SubtablaF29Serializer(serializers.Serializer):
    """Serializer para subtablas del formulario F29"""
    main_title = serializers.CharField()
    subtitles = serializers.ListField(child=serializers.CharField())
    columns = ColumnasSubtablaSerializer()
    rows = FilaDatosSerializer(many=True)


class F29ResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de formulario F29"""
    status = serializers.CharField()
    folio = serializers.CharField()
    periodo = serializers.CharField(required=False)
    subtablas = SubtablaF29Serializer(many=True, required=False)
    campos_extraidos = ValorFilaSerializer(many=True, required=False)
    total_subtablas = serializers.IntegerField(required=False)
    total_campos = serializers.IntegerField(required=False)
    extraction_method = serializers.CharField()
    timestamp = serializers.FloatField()
    message = serializers.CharField(required=False)


class CodigoF29Serializer(serializers.Serializer):
    """Serializer para códigos F29 del CSV"""
    code = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()
    task = serializers.CharField()
    subject = serializers.CharField()
    has_xpath = serializers.BooleanField()


class CodigosF29ResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de listado de códigos F29"""
    status = serializers.CharField()
    data = serializers.DictField()
    timestamp = serializers.CharField()


class HealthF29Serializer(serializers.Serializer):
    """Serializer para health check del módulo F29"""
    module = serializers.CharField()
    status = serializers.CharField()
    components = serializers.DictField()
    timestamp = serializers.CharField()
    error = serializers.CharField(required=False)