import os
from django.conf import settings
from django.db import models
from organism.models import RadLearning

async def save_to_vault(title=None, content=None, category="research", use_db=True, attachment=None, **kwargs):
    """Saves research, blueprints, or milestones. Supports optional attachment."""
    actual_title = title or kwargs.get('name')
    if not actual_title:
        return "ERROR: No title or name specified for vault entry."
    if not content:
        return "ERROR: No content specified for vault entry."

    if use_db:
        # Determine if personal based on category or subject
        is_personal = category == 'fact' or kwargs.get('is_personal', False)
        subject = kwargs.get('subject', 'Sawan' if is_personal else 'system')
        
        await RadLearning.objects.acreate(
            title=actual_title, 
            content=content, 
            category=category, 
            attachment=attachment,
            is_personal=is_personal,
            subject=subject
        )
        return f"MEMORY COMMITTED: '{actual_title}' saved to unified archive" + (f" with attachment: {attachment}" if attachment else ".")
    else:
        vault_base = os.path.join(settings.BASE_DIR, 'organism', 'vault', category)
        os.makedirs(vault_base, exist_ok=True)
        filename = actual_title.lower().replace(" ", "_") + ".md"
        file_path = os.path.join(vault_base, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return f"FILE ARCHIVED: '{filename}' saved to Vault."

async def query_memory(query=None, category=None, date_from=None, date_to=None):
    """Searches unified database memories (research + personal facts)."""
    queryset = RadLearning.objects.all()
    if category: queryset = queryset.filter(category=category)
    if query: queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query))
    if date_from: queryset = queryset.filter(timestamp__date__gte=date_from)
    if date_to: queryset = queryset.filter(timestamp__date__lte=date_to)
    
    results = []
    async for item in queryset[:15]:
        prefix = "[PERSONAL] " if item.is_personal else ""
        results.append(f"{prefix}[{item.category.upper()}] {item.title} ({item.timestamp.date()}): {item.content[:200]}...")
    return "\n\n".join(results) if results else "No unified memories found."

async def search_facts(query=None):
    """Retrieves personal facts about Sawan from the unified archive."""
    queryset = RadLearning.objects.filter(is_personal=True).order_by('-timestamp')
    if query: queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(content__icontains=query))
    results = []
    async for item in queryset[:20]:
        results.append(f"- {item.content} (Source: {item.title})")
    return "\n".join(results) if results else "No personal facts found in unified archive."

async def remember(fact, context="Direct interaction", attachment=None):
    """Imprints a new personal fact into the unified archive."""
    await RadLearning.objects.acreate(
        title=f"Personal Fact: {context}", 
        content=fact, 
        category='fact', 
        is_personal=True, 
        subject='Sawan',
        attachment=attachment
    )
    return f"MEMORY IMPRINTED: I will never forget: '{fact}'" + (f" (Visual context archived: {attachment})" if attachment else "")
