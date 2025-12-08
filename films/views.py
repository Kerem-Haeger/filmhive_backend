from rest_framework import viewsets
from .models import Film
from .serializers import FilmSerializer


class FilmViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Provides /api/films/  (list)
            /api/films/<id>/ (detail)
    """
    queryset = Film.objects.all()
    serializer_class = FilmSerializer
