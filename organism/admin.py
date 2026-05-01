from django.contrib import admin
from .models import APICall, SawanFact

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
