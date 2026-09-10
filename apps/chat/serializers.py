from rest_framework import serializers


class QuerySerializer(serializers.Serializer):
    thread_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(max_length=4000, trim_whitespace=True)

    def validate_message(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("پیام نمی‌تواند خالی باشد.")
        return value.strip()


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        trim_whitespace=True,
    )
