"""URL patterns para la aplicación de documentos."""

from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet


router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")

urlpatterns = router.urls