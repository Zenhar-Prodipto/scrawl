from rest_framework import serializers
from .models import Post, PostImage
from .services import create_post

class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ['image_url', 'order']

    def validate_image_url(self, value):
        if not value.startswith('http'):
            raise serializers.ValidationError("Image URL must start with 'http' or 'https'.")
        return value

class PostCreateSerializer(serializers.ModelSerializer):
    post_images = PostImageSerializer(many=True, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False, trim_whitespace=True),
        min_length=1,
        max_length=10
    )
    privacy = serializers.ChoiceField(choices=Post.PRIVACY_CHOICES, default='public')
    text = serializers.CharField(max_length=500, allow_blank=True, required=False)

    class Meta:
        model = Post
        fields = ['text', 'tags', 'privacy', 'post_images']

    def validate_text(self, value):
        if value and len(value) > 500:
            raise serializers.ValidationError("Text cannot exceed 500 characters.")
        return value

    def validate_tags(self, value):
        if not value or len(value) < 1:
            raise serializers.ValidationError("At least one tag is required.")
        for tag in value:
            tag = tag.strip()
            if not tag or len(tag) < 1:
                raise serializers.ValidationError("Each tag must be at least 1 character long and cannot be empty.")
            if len(tag) > 50:
                raise serializers.ValidationError("Each tag cannot exceed 50 characters.")
        return value

    def save(self, **kwargs):
        user = kwargs.pop('user')
        validated_data = dict(self.validated_data)
        tags_data = validated_data.pop('tags')
        return create_post(user, validated_data, tags_data)