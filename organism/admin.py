from django.contrib import admin
from .models import APICall, SawanFact, ChatMessage, RadTask, RadLearning

@admin.register(APICall)
class APICallAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'pollen_cost', 'prompt_preview')
    list_filter = ('timestamp',)
    readonly_fields = ('timestamp',)

    def prompt_preview(self, obj):
        return obj.prompt[:100]
    prompt_preview.short_description = 'Prompt Preview'

@admin.register(SawanFact)
class SawanFactAdmin(admin.ModelAdmin):
    list_display = ('fact', 'context', 'timestamp')
    list_filter = ('context', 'timestamp')
    search_fields = ('fact', 'context')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('role', 'timestamp', 'content_preview')
    list_filter = ('role', 'timestamp')
    search_fields = ('content',)

    def content_preview(self, obj):
        return obj.content[:100]

@admin.register(RadTask)
class RadTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'status', 'created_at')
    list_filter = ('priority', 'status', 'created_at')
    search_fields = ('title', 'description')
    list_editable = ('status', 'priority')

@admin.register(RadLearning)
class RadLearningAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'timestamp')
    list_filter = ('category', 'timestamp')
    search_fields = ('title', 'content')
