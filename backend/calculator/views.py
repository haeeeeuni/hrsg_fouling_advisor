"""계산기 API (specs/10 §4). 계산은 저장하지 않는다 — 부작용이 없어 디바운스 호출에 안전하다."""

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from calculator import runner
from calculator.serializers import LossInputSerializer, PinchInputSerializer


class OptionsView(APIView):
    def get(self, request: Request) -> Response:
        return Response(runner.options())


class LossView(APIView):
    def post(self, request: Request) -> Response:
        serializer = LossInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(runner.run_loss(serializer.validated_data))


class MethodsView(APIView):
    def post(self, request: Request) -> Response:
        serializer = LossInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(runner.run_methods(serializer.validated_data))


class PinchApproachView(APIView):
    def post(self, request: Request) -> Response:
        serializer = PinchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(runner.run_pinch(serializer.validated_data))
