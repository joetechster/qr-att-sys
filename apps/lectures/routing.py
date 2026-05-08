from django.urls import path

from .consumers import QRDisplayConsumer

websocket_urlpatterns = [
    path("ws/lectures/<int:lecture_id>/qr/", QRDisplayConsumer.as_asgi()),
]
