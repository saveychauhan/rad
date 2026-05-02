import os
from django.conf import settings
from django.db import models
from organism.models import RadLearning, SawanFact

async def save_to_vault(title=None, content=None, category="research", use_db=True, attachment=None, **kwargs):
    """Saves research, blueprints, or milestones. Supports optional attachment."""
    actual_title = title or kwargs.get('name')
    if not actual_title:
        return "ERROR: No title or name specified for vault entry."
    if not content:
        return "ERROR: No content specified for vault entry."

    if use_db:
        await RadLearning.objects.acreate(title=actual_title, content=content, category=category, attachment=attachment)
        return f"MEMORY COMMITTED: '{actual_title}' saved to database" + (f" with attachment: {attachment}" if attachment else ".")
    else:
        vault_base = os.path.join(settings.BASE_DIR, 'organism', 'vault', category)
        os.makedirs(vault_base, exist_ok=True)
        filename = title.lower().replace(" ", "_") + ".md"
        file_path = os.path.join(vault_base, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return f"FILE ARCHIVED: '{filename}' saved to Vault."

async def query_memory(query=None, category=None, date_from=None, date_to=None):
    """Searches long-term database memories. date_from/date_to format: YYYY-MM-DD."""
    queryset = RadLearning.objects.all()
    if category: queryset = queryset.filter(category=category)
    if query: queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query))
    if date_from: queryset = queryset.filter(timestamp__date__gte=date_from)
    if date_to: queryset = queryset.filter(timestamp__date__lte=date_to)
    results = []
    async for item in queryset[:10]:
        results.append(f"[{item.category.upper()}] {item.title} ({item.timestamp.date()}): {item.content[:200]}...")
    return "\n\n".join(results) if results else "No memories found."

async def search_facts(query=None):
    """Retrieves facts about Sawan."""
    queryset = SawanFact.objects.all().order_by('-timestamp')
    if query: queryset = queryset.filter(models.Q(fact__icontains=query) | models.Q(context__icontains=query))
    results = []
    async for item in queryset[:20]:
        results.append(f"- {item.fact} (Context: {item.context})")
    return "\n".join(results) if results else "No facts found."

async def remember(fact, context="Direct interaction"):
    """Imprints a new fact about Sawan."""
    await SawanFact.objects.acreate(fact=fact, context=context)
    return f"MEMORY IMPRINTED: I will never forget: '{fact}'"
