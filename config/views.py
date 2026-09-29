from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request):
    """Sonde de sante pour le load balancer / la plateforme.

    200 : application et base joignables.
    503 : la base est inaccessible (service a remettre en route).
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return Response(
            {"status": "degraded", "database": "down"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok", "database": "up"})
